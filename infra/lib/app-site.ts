import { execFileSync } from "node:child_process";
import { cpSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { CfnOutput, DockerImage, Duration, Fn, RemovalPolicy, Stack } from "aws-cdk-lib";
import { type HttpApi, HttpMethod, type HttpRoute } from "aws-cdk-lib/aws-apigatewayv2";
import { HttpLambdaIntegration } from "aws-cdk-lib/aws-apigatewayv2-integrations";
import {
  AllowedMethods,
  CachePolicy,
  Distribution,
  OriginRequestPolicy,
  ViewerProtocolPolicy,
} from "aws-cdk-lib/aws-cloudfront";
import { HttpOrigin, S3BucketOrigin } from "aws-cdk-lib/aws-cloudfront-origins";
import type { Table } from "aws-cdk-lib/aws-dynamodb";
import { Architecture, type Code, Function as LambdaFn, Runtime } from "aws-cdk-lib/aws-lambda";
import type { LogGroup } from "aws-cdk-lib/aws-logs";
import { BlockPublicAccess, Bucket, BucketEncryption, type IBucket } from "aws-cdk-lib/aws-s3";
import { BucketDeployment, Source } from "aws-cdk-lib/aws-s3-deployment";
import type { ISecret } from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";

const PWA_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../pwa");

export interface AppSiteProps {
  api: HttpApi;
  code: Code;
  baseEnvironment: Record<string, string>;
  table: Table;
  appSecret: ISecret;
  tokenSecret: ISecret;
  stillsBucket: IBucket;
  logGroup: (id: string) => LogGroup;
  /** IANA zone for "today" in answers to fridge questions. */
  timeZone: string;
}

/** The phone app: an /api Lambda on the HTTP API, and the PWA on S3 + CloudFront. */
export class AppSite extends Construct {
  readonly url: string;
  /** `POST /api/session`, its own route so the stage can throttle the passcode check. */
  readonly sessionRoute: HttpRoute;

  constructor(scope: Construct, id: string, props: AppSiteProps) {
    super(scope, id);
    const stack = Stack.of(this);

    const fn = new LambdaFn(this, "ApiFunction", {
      code: props.code,
      handler: "fridgesense.handlers.api.handler",
      runtime: Runtime.PYTHON_3_13,
      architecture: Architecture.ARM_64,
      memorySize: 256,
      timeout: Duration.seconds(10),
      logGroup: props.logGroup("ApiFunction"),
      description: "App API: sign-in, inventory, door events, pending changes, questions",
      environment: {
        ...props.baseEnvironment,
        STILLS_BUCKET: props.stillsBucket.bucketName,
        TIME_ZONE: props.timeZone,
      },
    });
    props.table.grantReadWriteData(fn);
    props.appSecret.grantRead(fn);
    props.tokenSecret.grantRead(fn);
    props.stillsBucket.grantRead(fn);

    const integration = new HttpLambdaIntegration("AppApiIntegration", fn);
    props.api.addRoutes({ path: "/api/{proxy+}", methods: [HttpMethod.ANY], integration });
    [this.sessionRoute] = props.api.addRoutes({
      path: "/api/session",
      methods: [HttpMethod.POST],
      integration,
    });

    const site = new Bucket(this, "Site", {
      bucketName: `fridgesense-site-${stack.account}`,
      blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
      encryption: BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // https://<id>.execute-api.<region>.amazonaws.com → <id>.execute-api.<region>.amazonaws.com
    const apiDomain = Fn.select(2, Fn.split("/", props.api.apiEndpoint));
    const distribution = new Distribution(this, "Distribution", {
      comment: "FridgeSense app",
      defaultRootObject: "index.html",
      defaultBehavior: {
        origin: S3BucketOrigin.withOriginAccessControl(site),
        viewerProtocolPolicy: ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      },
      additionalBehaviors: {
        "/api/*": {
          origin: new HttpOrigin(apiDomain),
          viewerProtocolPolicy: ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: AllowedMethods.ALLOW_ALL,
          cachePolicy: CachePolicy.CACHING_DISABLED,
          originRequestPolicy: OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
        },
      },
      // No errorResponses: they would also rewrite /api/* errors, and the app routes by #hash.
    });

    new BucketDeployment(this, "Deploy", {
      sources: [pwaBuild()],
      destinationBucket: site,
      distribution,
      distributionPaths: ["/*"],
    });

    this.url = `https://${distribution.distributionDomainName}`;
    new CfnOutput(stack, "SiteUrl", { value: this.url });
  }
}

/** The PWA's production build (`npm ci && npm run build` in pwa/). */
function pwaBuild() {
  return Source.asset(PWA_DIR, {
    exclude: ["node_modules", "dist", "coverage"],
    bundling: {
      image: DockerImage.fromRegistry("node:22"),
      command: ["bash", "-c", "npm ci && npm run build && cp -r dist/. /asset-output/"],
      local: {
        tryBundle(outputDir: string) {
          execFileSync("npm", ["ci"], { cwd: PWA_DIR, stdio: "inherit" });
          execFileSync("npm", ["run", "build"], { cwd: PWA_DIR, stdio: "inherit" });
          cpSync(path.join(PWA_DIR, "dist"), outputDir, { recursive: true });
          return true;
        },
      },
    },
  });
}
