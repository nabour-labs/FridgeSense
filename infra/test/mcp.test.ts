import { Match, type Template } from "aws-cdk-lib/assertions";
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

function mcpFunction(): [string, Resource] {
  const found = Object.entries(resourcesOf("AWS::Lambda::Function")).filter(
    ([, r]) => r.Properties.Handler === "fridgesense.handlers.mcp.handler",
  );
  expect(found).toHaveLength(1);
  return found[0];
}

function actionsFor(logicalId: string): string[] {
  const prefix = logicalId.replace(/[A-F0-9]{8}$/, "");
  return Object.values(resourcesOf("AWS::IAM::Policy"))
    .filter((p) => JSON.stringify(p.Properties.Roles).includes(prefix))
    .flatMap((p) => (p.Properties.PolicyDocument as { Statement: Statement[] }).Statement)
    .flatMap((s) => [s.Action].flat());
}

describe("MCP server", () => {
  it("is an arm64 Lambda with 512 MB, 10 s and the household time zone", () => {
    const [, fn] = mcpFunction();
    expect(fn.Properties.Runtime).toBe("python3.13");
    expect(fn.Properties.Architectures).toEqual(["arm64"]);
    expect(fn.Properties.MemorySize).toBe(512);
    expect(fn.Properties.Timeout).toBe(10);
    const vars = (fn.Properties.Environment as { Variables: Record<string, unknown> }).Variables;
    expect(vars.TIME_ZONE).toBe("America/Toronto");
    expect(Object.keys(vars).sort()).toEqual([
      "RING_APP_SECRET_ID",
      "RING_TOKENS_SECRET_ID",
      "TABLE_NAME",
      "TIME_ZONE",
    ]);
  });

  it("logs to /fridgesense/mcp", () => {
    const names = Object.values(resourcesOf("AWS::Logs::LogGroup")).map((g) => g.Properties.LogGroupName);
    expect(names).toContain("/fridgesense/mcp");
  });

  it("is reachable at ANY /mcp/{key}", () => {
    const routes = Object.values(resourcesOf("AWS::ApiGatewayV2::Route")).map((r) => r.Properties.RouteKey);
    expect(routes).toContain("ANY /mcp/{key}");
  });

  it("is kept warm every 5 minutes with a warm-up event", () => {
    template.hasResourceProperties("AWS::Events::Rule", {
      ScheduleExpression: "rate(5 minutes)",
      Targets: Match.arrayWith([Match.objectLike({ Input: JSON.stringify({ warmup: true }) })]),
    });
  });

  it("can only read the table and secrets, and nothing else", () => {
    const [id] = mcpFunction();
    const actions = actionsFor(id);
    expect(actions).toEqual(expect.arrayContaining(["dynamodb:Query", "dynamodb:GetItem"]));
    expect(actions.filter((a) => /^dynamodb:(Put|Update|Delete|BatchWrite)/.test(a))).toEqual([]);
    expect(actions).toContain("secretsmanager:GetSecretValue");
    expect(actions.filter((a) => /^secretsmanager:(Put|Update)/.test(a))).toEqual([]);
    expect(actions.filter((a) => /^(bedrock|s3|states|rekognition):/.test(a))).toEqual([]);
  });
});
