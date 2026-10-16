import { execFileSync } from "node:child_process";
import { cpSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  CfnOutput,
  Duration,
  RemovalPolicy,
  SecretValue,
  Stack,
  type StackProps,
} from "aws-cdk-lib";
import { CfnStage, HttpApi, HttpMethod, type HttpRoute } from "aws-cdk-lib/aws-apigatewayv2";
import { HttpLambdaIntegration } from "aws-cdk-lib/aws-apigatewayv2-integrations";
import { CfnBudget } from "aws-cdk-lib/aws-budgets";
import {
  Alarm,
  ComparisonOperator,
  Stats,
  TreatMissingData,
} from "aws-cdk-lib/aws-cloudwatch";
import { SnsAction } from "aws-cdk-lib/aws-cloudwatch-actions";
import { AttributeType, BillingMode, Table } from "aws-cdk-lib/aws-dynamodb";
import { Rule, Schedule } from "aws-cdk-lib/aws-events";
import { LambdaFunction } from "aws-cdk-lib/aws-events-targets";
import { Architecture, Code, Function as LambdaFn, Runtime } from "aws-cdk-lib/aws-lambda";
import { LogGroup, RetentionDays } from "aws-cdk-lib/aws-logs";
import { Secret } from "aws-cdk-lib/aws-secretsmanager";
import { Topic } from "aws-cdk-lib/aws-sns";
import { EmailSubscription } from "aws-cdk-lib/aws-sns-subscriptions";
import type { Construct } from "constructs";
import { AppSite } from "./app-site.js";
import { DoorPipeline } from "./door-pipeline.js";
import { McpEndpoint } from "./mcp-endpoint.js";

const BACKEND_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../backend");

/**
 * The backend package and its locked dependencies, built for Lambda arm64 with uv (no Docker):
 * dependencies come from uv.lock as arm64 wheels, then the package source is copied in.
 */
function backendCode(): Code {
  return Code.fromAsset(BACKEND_DIR, {
    exclude: [".venv", "tests", ".pytest_cache", ".ruff_cache", "**/__pycache__", "build", "dist"],
    bundling: {
      image: Runtime.PYTHON_3_13.bundlingImage,
      command: ["bash", "-c", "pip install --target /asset-output /asset-input"],
      local: {
        tryBundle(outputDir: string) {
          const requirements = path.join(outputDir, "..", `requirements-${path.basename(outputDir)}.txt`);
          const uv = (args: string[]) =>
            execFileSync("uv", args, { cwd: BACKEND_DIR, stdio: "inherit" });
          uv([
            "export",
            "--frozen",
            "--no-dev",
            "--no-emit-project",
            "--no-hashes",
            "--quiet",
            "--output-file",
            requirements,
          ]);
          uv([
            "pip",
            "install",
            "--requirements",
            requirements,
            "--target",
            outputDir,
            "--python-platform",
            "aarch64-manylinux_2_28", // Lambda python3.13 runs on Amazon Linux 2023 (glibc 2.34)
            "--python-version",
            "3.13",
            "--only-binary",
            ":all:",
          ]);
          rmSync(requirements);
          cpSync(path.join(BACKEND_DIR, "src", "fridgesense"), path.join(outputDir, "fridgesense"), {
            recursive: true,
            filter: (src) => !src.includes("__pycache__"),
          });
          return true;
        },
      },
    },
  });
}

export class FridgeSenseStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Budget and alarm emails go here; never commit an address: cdk deploy -c alertEmail=...
    const alertEmail = String(this.node.tryGetContext("alertEmail") ?? "");
    if (!alertEmail) {
      throw new Error("Set the alert email: cdk deploy -c alertEmail=you@example.com");
    }

    const table = new Table(this, "Table", {
      tableName: "fridgesense",
      partitionKey: { name: "pk", type: AttributeType.STRING },
      sortKey: { name: "sk", type: AttributeType.STRING },
      billingMode: BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: "ttl",
      removalPolicy: RemovalPolicy.RETAIN,
    });

    // Jayson fills in client_id, client_secret and hmac_key; the passcode is generated.
    const appSecret = new Secret(this, "RingAppSecret", {
      secretName: "fridgesense/ring-app",
      description: "Ring private app credentials and the FridgeSense link passcode",
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ client_id: "", client_secret: "", hmac_key: "" }),
        generateStringKey: "passcode",
        passwordLength: 32,
        excludePunctuation: true,
      },
      removalPolicy: RemovalPolicy.RETAIN,
    });

    // Written only by the Lambdas.
    const tokenSecret = new Secret(this, "RingTokensSecret", {
      secretName: "fridgesense/ring-tokens",
      description: "Ring OAuth tokens for the linked account",
      secretStringValue: SecretValue.unsafePlainText("{}"),
    });

    const logGroupNames: Record<string, string> = {
      HttpFunction: "/fridgesense/http",
      TokenRefreshFunction: "/fridgesense/token-refresh",
      PipelineFunction: "/fridgesense/pipeline",
      ApiFunction: "/fridgesense/api",
      McpFunction: "/fridgesense/mcp",
    };
    const logGroup = (id: string) =>
      new LogGroup(this, `${id}Logs`, {
        logGroupName: logGroupNames[id],
        retention: RetentionDays.TWO_WEEKS,
        removalPolicy: RemovalPolicy.DESTROY,
      });

    const code = backendCode();
    const common = {
      code,
      runtime: Runtime.PYTHON_3_13,
      architecture: Architecture.ARM_64,
      timeout: Duration.seconds(10),
      memorySize: 256,
      environment: {
        RING_APP_SECRET_ID: appSecret.secretName,
        RING_TOKENS_SECRET_ID: tokenSecret.secretName,
        TABLE_NAME: table.tableName,
      },
    };

    const context = (key: string, fallback: string) =>
      String(this.node.tryGetContext(key) ?? fallback);
    const nova = {
      novaModelId: context("novaModelId", "us.amazon.nova-2-lite-v1:0"),
      novaPriceIn: context("novaPriceIn", "0.00033"),
      novaPriceOut: context("novaPriceOut", "0.00275"),
      // Nova 2 Lite in us-east-1: cache reads at a quarter of the input price, writes free.
      novaPriceCacheRead: context("novaPriceCacheRead", "0.0000825"),
      novaPriceCacheWrite: context("novaPriceCacheWrite", "0"),
    };
    // "today" in fridge answers and usage totals means the household's day:
    // cdk deploy -c timeZone=America/Vancouver
    const timeZone = context("timeZone", "America/Toronto");
    // Used until the owner runs setup on the app's Open/close detection tab.
    // Re-tune with -c doorZones=x,y,w,h;x,y,w,h -c doorThreshold=0.02
    const doorZones = context("doorZones", "0.38,0.32,0.21,0.30;0.455,0.60,0.12,0.18");
    const doorThreshold = context("doorThreshold", "0.02");
    const doors = new DoorPipeline(this, "Doors", {
      code,
      baseEnvironment: common.environment,
      table,
      appSecret,
      tokenSecret,
      logGroup,
      doorZones,
      doorThreshold,
      // The visible strip the camera's privacy mask leaves; -c stillCrop= keeps the full frame
      stillCrop: context("stillCrop", "0.30,0.0,0.34,1.0"),
      // About one still per second across each motion window: -c stillIntervalMs=2000
      stillIntervalMs: context("stillIntervalMs", "1000"),
      ...nova,
      // Turn on once measured: cdk deploy -c novaCacheAnalysis=true
      novaCacheAnalysis: context("novaCacheAnalysis", "false"),
      timeZone,
      faceDetectPrice: context("faceDetectPrice", "0.001"),
    });

    const httpFn = new LambdaFn(this, "HttpFunction", {
      ...common,
      environment: {
        ...common.environment,
        STATE_MACHINE_ARN: doors.stateMachine.stateMachineArn,
      },
      handler: "fridgesense.handlers.http.handler",
      logGroup: logGroup("HttpFunction"),
      description: "Ring token exchange, account link page and webhook",
    });
    appSecret.grantRead(httpFn);
    tokenSecret.grantRead(httpFn);
    tokenSecret.grantWrite(httpFn);
    table.grantReadWriteData(httpFn);
    doors.stateMachine.grantStartExecution(httpFn);

    const refreshFn = new LambdaFn(this, "TokenRefreshFunction", {
      ...common,
      handler: "fridgesense.handlers.token_refresh.handler",
      logGroup: logGroup("TokenRefreshFunction"),
      description: "Refreshes the Ring tokens every 3 hours",
    });
    appSecret.grantRead(refreshFn);
    tokenSecret.grantRead(refreshFn);
    tokenSecret.grantWrite(refreshFn);

    new Rule(this, "TokenRefreshSchedule", {
      schedule: Schedule.rate(Duration.hours(3)),
      targets: [new LambdaFunction(refreshFn)],
    });

    const api = new HttpApi(this, "Api", { apiName: "fridgesense" });
    const integration = new HttpLambdaIntegration("HttpIntegration", httpFn);
    const routes: [string, HttpMethod][] = [
      ["/ring/token", HttpMethod.POST],
      ["/ring/link", HttpMethod.GET],
      ["/ring/webhook", HttpMethod.POST],
    ];
    for (const [routePath, method] of routes) {
      api.addRoutes({ path: routePath, methods: [method], integration });
    }
    // The link page's passcode check: throttled on its own below.
    const [ringLinkPost] = api.addRoutes({
      path: "/ring/link",
      methods: [HttpMethod.POST],
      integration,
    });


    const app = new AppSite(this, "App", {
      api,
      code,
      baseEnvironment: common.environment,
      table,
      appSecret,
      tokenSecret,
      stillsBucket: doors.bucket,
      logGroup,
      timeZone,
      // The Ask screen's assistant; switch off with: cdk deploy -c askAgent=off
      askAgent: context("askAgent", "on"),
      askAgentDailyLimit: context("askAgentDailyLimit", "100"),
      doorZones,
      doorThreshold,
      faceDetectPrice: context("faceDetectPrice", "0.001"),
      ...nova,
    });
    // Throttle the API; the two passcode checks much harder to slow brute force.
    // Limits are per route across all callers. API Gateway rejects route settings
    // for routes that don't exist yet, so the stage waits for them.
    const stage = api.defaultStage?.node.defaultChild as CfnStage;
    stage.defaultRouteSettings = { throttlingRateLimit: 10, throttlingBurstLimit: 20 };
    const passcodeRoutes: [string, HttpRoute][] = [
      ["POST /api/session", app.sessionRoute],
      ["POST /ring/link", ringLinkPost],
    ];
    // RouteSettings is an untyped map: CDK passes its keys through as written.
    stage.routeSettings = Object.fromEntries(
      passcodeRoutes.map(([key]) => [key, { ThrottlingRateLimit: 1, ThrottlingBurstLimit: 3 }]),
    );
    for (const [, route] of passcodeRoutes) stage.node.addDependency(route);

    // The "Camera linked" page links to the app.
    httpFn.addEnvironment("APP_URL", app.url);

    new McpEndpoint(this, "Mcp", {
      api,
      code,
      baseEnvironment: common.environment,
      table,
      appSecret,
      tokenSecret,
      logGroup,
      timeZone,
    });

    // Cost and failure alerts, by email.
    new CfnBudget(this, "MonthlyBudget", {
      budget: {
        budgetName: "fridgesense-monthly",
        budgetType: "COST",
        timeUnit: "MONTHLY",
        budgetLimit: { amount: 20, unit: "USD" },
      },
      notificationsWithSubscribers: [
        {
          notification: {
            notificationType: "ACTUAL",
            comparisonOperator: "GREATER_THAN",
            threshold: 80,
            thresholdType: "PERCENTAGE",
          },
          subscribers: [{ subscriptionType: "EMAIL", address: alertEmail }],
        },
      ],
    });
    const alerts = new Topic(this, "Alerts", { topicName: "fridgesense-alerts" });
    alerts.addSubscription(new EmailSubscription(alertEmail));
    new Alarm(this, "DoorEventsFailed", {
      alarmName: "fridgesense-door-events-failed",
      alarmDescription: "A door-event workflow run failed",
      metric: doors.stateMachine.metricFailed({ period: Duration.minutes(5), statistic: Stats.SUM }),
      threshold: 1,
      comparisonOperator: ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      evaluationPeriods: 1,
      treatMissingData: TreatMissingData.NOT_BREACHING,
    }).addAlarmAction(new SnsAction(alerts));

    const base = api.apiEndpoint;
    new CfnOutput(this, "TokenExchangeUrl", { value: `${base}/ring/token` });
    new CfnOutput(this, "AccountLinkUrl", { value: `${base}/ring/link` });
    new CfnOutput(this, "WebhookUrl", { value: `${base}/ring/webhook` });
  }
}
