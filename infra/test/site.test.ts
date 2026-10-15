import type { Template } from "aws-cdk-lib/assertions";
import { beforeAll, describe, expect, it } from "vitest";
import { synthTemplate } from "./helpers.js";

let template: Template;

type Resource = { Properties: Record<string, unknown> };
type Statement = { Action: string | string[]; Resource: unknown };

beforeAll(() => {
  template = synthTemplate();
});

function resourcesOf(type: string): Record<string, Resource> {
  return template.findResources(type) as Record<string, Resource>;
}

function apiFunction(): [string, Resource] {
  const found = Object.entries(resourcesOf("AWS::Lambda::Function")).filter(
    ([, r]) => r.Properties.Handler === "fridgesense.handlers.api.handler",
  );
  expect(found).toHaveLength(1);
  return found[0];
}

function statementsFor(logicalId: string): Statement[] {
  const prefix = logicalId.replace(/[A-F0-9]{8}$/, "");
  return Object.values(resourcesOf("AWS::IAM::Policy"))
    .filter((p) => JSON.stringify(p.Properties.Roles).includes(prefix))
    .flatMap((p) => (p.Properties.PolicyDocument as { Statement: Statement[] }).Statement);
}

const actionsOf = (stmts: Statement[]) => stmts.flatMap((s) => [s.Action].flat());

// CloudFront managed policy IDs (AWS-wide constants).
const CACHING_DISABLED = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad";
const ALL_VIEWER_EXCEPT_HOST = "b689b0a8-53d0-40ab-baf2-68738e2966ac";

describe("app API", () => {
  it("is a Python 3.13 arm64 Lambda with 256 MB, 20 s and the household time zone", () => {
    const [, fn] = apiFunction();
    expect(fn.Properties.Runtime).toBe("python3.13");
    expect(fn.Properties.Architectures).toEqual(["arm64"]);
    expect(fn.Properties.MemorySize).toBe(256);
    expect(fn.Properties.Timeout).toBe(20);
    const vars = (fn.Properties.Environment as { Variables: Record<string, unknown> }).Variables;
    expect(Object.keys(vars).sort()).toEqual([
      "ASK_AGENT",
      "ASK_AGENT_DAILY_LIMIT",
      "NOVA_MODEL_ID",
      "NOVA_PRICE_CACHE_READ",
      "NOVA_PRICE_CACHE_WRITE",
      "NOVA_PRICE_IN",
      "NOVA_PRICE_OUT",
      "RING_APP_SECRET_ID",
      "RING_TOKENS_SECRET_ID",
      "STILLS_BUCKET",
      "TABLE_NAME",
      "TIME_ZONE",
    ]);
    expect(vars.TIME_ZONE).toBe("America/Toronto");
  });

  it("takes the time zone from the timeZone context", () => {
    const other = synthTemplate({ timeZone: "America/Vancouver" });
    const fns = Object.values(other.findResources("AWS::Lambda::Function") as Record<string, Resource>);
    const fn = fns.find((r) => r.Properties.Handler === "fridgesense.handlers.api.handler")!;
    const vars = (fn.Properties.Environment as { Variables: Record<string, unknown> }).Variables;
    expect(vars.TIME_ZONE).toBe("America/Vancouver");
  });

  it("can switch the assistant off with the askAgent context", () => {
    const other = synthTemplate({ askAgent: "off", askAgentDailyLimit: "20" });
    const fns = Object.values(other.findResources("AWS::Lambda::Function") as Record<string, Resource>);
    const fn = fns.find((r) => r.Properties.Handler === "fridgesense.handlers.api.handler")!;
    const vars = (fn.Properties.Environment as { Variables: Record<string, unknown> }).Variables;
    expect(vars.ASK_AGENT).toBe("off");
    expect(vars.ASK_AGENT_DAILY_LIMIT).toBe("20");
  });

  it("serves every /api path through one catch-all route", () => {
    const routes = Object.values(resourcesOf("AWS::ApiGatewayV2::Route")).map((r) => r.Properties.RouteKey);
    expect(routes).toContain("ANY /api/{proxy+}");
  });

  it("can use the table, read both secrets and only read stills", () => {
    const [id] = apiFunction();
    const stmts = statementsFor(id);
    const actions = actionsOf(stmts);
    // Transactions are authorized by the per-item actions.
    expect(actions).toEqual(
      expect.arrayContaining(["dynamodb:Query", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem"]),
    );
    expect(actions).toContain("secretsmanager:GetSecretValue");
    expect(actions.filter((a) => a.startsWith("secretsmanager:Put"))).toEqual([]);
    const s3 = actions.filter((a) => a.startsWith("s3:"));
    expect(s3).toEqual(expect.arrayContaining(["s3:GetObject*"]));
    expect(s3.filter((a) => /Put|Delete/.test(a))).toEqual([]);
    // Bedrock only to invoke Nova for the Ask assistant; never the state machine.
    expect(actions.filter((a) => a.startsWith("bedrock:"))).toEqual(["bedrock:InvokeModel"]);
    expect(actions.filter((a) => a.startsWith("states:"))).toEqual([]);
  });
});

describe("site", () => {
  it("keeps the site bucket private", () => {
    const buckets = Object.values(resourcesOf("AWS::S3::Bucket"));
    const site = buckets.find((b) => JSON.stringify(b.Properties.BucketName ?? "").includes("fridgesense-site"));
    expect(site).toBeDefined();
    expect(site!.Properties.PublicAccessBlockConfiguration).toEqual({
      BlockPublicAcls: true,
      BlockPublicPolicy: true,
      IgnorePublicAcls: true,
      RestrictPublicBuckets: true,
    });
  });

  it("serves the app through CloudFront with an origin access control", () => {
    expect(Object.keys(resourcesOf("AWS::CloudFront::OriginAccessControl"))).toHaveLength(1);
    const [dist] = Object.values(resourcesOf("AWS::CloudFront::Distribution"));
    const config = dist.Properties.DistributionConfig as Record<string, unknown>;
    // App shell at the root
    expect(config.DefaultRootObject).toBe("index.html");
  });

  it("passes API errors through: viewer write refused / not found through the CDN", () => {
    // Custom error responses apply to every origin, /api/* included; the app uses hash routes.
    const [dist] = Object.values(resourcesOf("AWS::CloudFront::Distribution"));
    const config = dist.Properties.DistributionConfig as Record<string, unknown>;
    expect(config.CustomErrorResponses).toBeUndefined();
  });

  it("routes /api/* to the HTTP API without caching", () => {
    const [dist] = Object.values(resourcesOf("AWS::CloudFront::Distribution"));
    const config = dist.Properties.DistributionConfig as {
      CacheBehaviors: Record<string, unknown>[];
      Origins: { Id: string; DomainName: unknown; S3OriginConfig?: unknown }[];
    };
    const api = config.CacheBehaviors.find((b) => b.PathPattern === "/api/*");
    expect(api).toMatchObject({
      CachePolicyId: CACHING_DISABLED,
      OriginRequestPolicyId: ALL_VIEWER_EXCEPT_HOST,
      AllowedMethods: ["GET", "HEAD", "OPTIONS", "PUT", "PATCH", "POST", "DELETE"],
      ViewerProtocolPolicy: "redirect-to-https",
    });
    const origin = config.Origins.find((o) => o.Id === api!.TargetOriginId);
    expect(JSON.stringify(origin!.DomainName)).toContain("Api");
  });

  it("deploys the built app and outputs the site URL", () => {
    expect(Object.keys(resourcesOf("Custom::CDKBucketDeployment"))).toHaveLength(1);
    expect(Object.keys(template.toJSON().Outputs ?? {})).toContain("SiteUrl");
  });
});
