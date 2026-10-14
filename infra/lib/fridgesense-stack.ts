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
import { HttpApi, HttpMethod } from "aws-cdk-lib/aws-apigatewayv2";
import { HttpLambdaIntegration } from "aws-cdk-lib/aws-apigatewayv2-integrations";
import { AttributeType, BillingMode, Table } from "aws-cdk-lib/aws-dynamodb";
import { Rule, Schedule } from "aws-cdk-lib/aws-events";
import { LambdaFunction } from "aws-cdk-lib/aws-events-targets";
import { Architecture, Code, Function as LambdaFn, Runtime } from "aws-cdk-lib/aws-lambda";
import { LogGroup, RetentionDays } from "aws-cdk-lib/aws-logs";
import { Secret } from "aws-cdk-lib/aws-secretsmanager";
import type { Construct } from "constructs";

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
            "aarch64-manylinux2014",
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

    const logGroup = (id: string) =>
      new LogGroup(this, `${id}Logs`, {
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

    const httpFn = new LambdaFn(this, "HttpFunction", {
      ...common,
      handler: "fridgesense.handlers.http.handler",
      logGroup: logGroup("HttpFunction"),
      description: "Ring token exchange, account link page and webhook",
    });
    appSecret.grantRead(httpFn);
    tokenSecret.grantRead(httpFn);
    tokenSecret.grantWrite(httpFn);
    table.grantReadWriteData(httpFn);

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
      ["/ring/link", HttpMethod.POST],
      ["/ring/webhook", HttpMethod.POST],
    ];
    for (const [routePath, method] of routes) {
      api.addRoutes({ path: routePath, methods: [method], integration });
    }

    const base = api.apiEndpoint;
    new CfnOutput(this, "TokenExchangeUrl", { value: `${base}/ring/token` });
    new CfnOutput(this, "AccountLinkUrl", { value: `${base}/ring/link` });
    new CfnOutput(this, "WebhookUrl", { value: `${base}/ring/webhook` });
  }
}
