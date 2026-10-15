import { Match, type Template } from "aws-cdk-lib/assertions";
import { beforeAll, describe, expect, it } from "vitest";
import { synthTemplate } from "./helpers.js";

let template: Template;

beforeAll(() => {
  template = synthTemplate();
});

type Resource = { Properties: Record<string, unknown> };

function resourcesOf(type: string): Record<string, Resource> {
  return template.findResources(type) as Record<string, Resource>;
}

describe("HTTP API", () => {
  it("has exactly the four Ring routes", () => {
    const routes = Object.values(resourcesOf("AWS::ApiGatewayV2::Route")).map(
      (r) => r.Properties.RouteKey,
    );
    expect(routes.sort()).toEqual([
      "GET /ring/link",
      "POST /ring/link",
      "POST /ring/token",
      "POST /ring/webhook",
    ]);
  });

  it("outputs the three URLs for the Ring developer console", () => {
    const outputs = Object.keys(template.toJSON().Outputs ?? {});
    expect(outputs).toEqual(
      expect.arrayContaining(["TokenExchangeUrl", "AccountLinkUrl", "WebhookUrl"]),
    );
  });
});

describe("Lambdas", () => {
  it("are three Python 3.13 arm64 functions", () => {
    const fns = Object.values(resourcesOf("AWS::Lambda::Function")).filter(
      (f) => f.Properties.Runtime === "python3.13",
    );
    expect(fns.map((f) => f.Properties.Handler).sort()).toEqual([
      "fridgesense.handlers.http.handler",
      "fridgesense.handlers.pipeline.handler",
      "fridgesense.handlers.token_refresh.handler",
    ]);
    for (const fn of fns) expect(fn.Properties.Architectures).toEqual(["arm64"]);
  });

  it("run the Ring endpoints and token refresh with 256 MB, 10 s and the shared env vars", () => {
    const expected: Record<string, string[]> = {
      "fridgesense.handlers.http.handler": [
        "RING_APP_SECRET_ID",
        "RING_TOKENS_SECRET_ID",
        "STATE_MACHINE_ARN",
        "TABLE_NAME",
      ],
      "fridgesense.handlers.token_refresh.handler": [
        "RING_APP_SECRET_ID",
        "RING_TOKENS_SECRET_ID",
        "TABLE_NAME",
      ],
    };
    for (const [handler, vars] of Object.entries(expected)) {
      const [fn] = Object.values(resourcesOf("AWS::Lambda::Function")).filter(
        (f) => f.Properties.Handler === handler,
      );
      expect(fn.Properties.Timeout).toBe(10);
      expect(fn.Properties.MemorySize).toBe(256);
      const env = (fn.Properties.Environment as { Variables: Record<string, unknown> }).Variables;
      expect(Object.keys(env).sort()).toEqual(vars);
    }
  });

  it("refreshes Ring tokens every 3 hours", () => {
    template.hasResourceProperties("AWS::Events::Rule", {
      ScheduleExpression: "rate(3 hours)",
      Targets: Match.arrayWith([Match.objectLike({ Arn: Match.anyValue() })]),
    });
  });
});

describe("Secrets", () => {
  it("creates the app config secret with a generated passcode and kept on delete", () => {
    template.hasResource("AWS::SecretsManager::Secret", {
      DeletionPolicy: "Retain",
      Properties: {
        Name: "fridgesense/ring-app",
        GenerateSecretString: Match.objectLike({
          GenerateStringKey: "passcode",
          SecretStringTemplate: JSON.stringify({ client_id: "", client_secret: "", hmac_key: "" }),
        }),
      },
    });
  });

  it("creates an empty token secret", () => {
    template.hasResourceProperties("AWS::SecretsManager::Secret", {
      Name: "fridgesense/ring-tokens",
      SecretString: "{}",
    });
  });
});

describe("Table", () => {
  it("is the on-demand single table with TTL, kept on delete", () => {
    template.hasResource("AWS::DynamoDB::Table", {
      DeletionPolicy: "Retain",
      Properties: {
        TableName: "fridgesense",
        BillingMode: "PAY_PER_REQUEST",
        KeySchema: [
          { AttributeName: "pk", KeyType: "HASH" },
          { AttributeName: "sk", KeyType: "RANGE" },
        ],
        TimeToLiveSpecification: { AttributeName: "ttl", Enabled: true },
      },
    });
  });
});

describe("IAM", () => {
  type Statement = { Action: string | string[]; Resource: unknown };

  function statementsFor(roleLogicalIdPrefix: string): Statement[] {
    return Object.values(resourcesOf("AWS::IAM::Policy"))
      .filter((p) =>
        JSON.stringify(p.Properties.Roles).includes(roleLogicalIdPrefix),
      )
      .flatMap(
        (p) => (p.Properties.PolicyDocument as { Statement: Statement[] }).Statement,
      );
  }

  const actions = (s: Statement) => [s.Action].flat();
  const resource = (s: Statement) => JSON.stringify(s.Resource);

  it.each(["HttpFunction", "TokenRefreshFunction"])(
    "%s reads the app secret but never writes it",
    (fn) => {
      const stmts = statementsFor(`${fn}ServiceRole`);
      const onApp = stmts.filter((s) => resource(s).includes("RingAppSecret"));
      expect(onApp.flatMap(actions)).toContain("secretsmanager:GetSecretValue");
      expect(onApp.flatMap(actions).filter((a) => a.includes("Put") || a.includes("Update"))).toEqual([]);
    },
  );

  it.each(["HttpFunction", "TokenRefreshFunction"])(
    "%s writes only the token secret",
    (fn) => {
      const writes = statementsFor(`${fn}ServiceRole`).filter((s) =>
        actions(s).some((a) => a.startsWith("secretsmanager:Put")),
      );
      expect(writes.length).toBeGreaterThan(0);
      for (const s of writes) expect(resource(s)).toMatch(/RingTokensSecret/);
    },
  );

  it("never grants secrets or table access on every resource", () => {
    for (const fn of ["HttpFunction", "TokenRefreshFunction"]) {
      for (const s of statementsFor(`${fn}ServiceRole`)) {
        const scoped = actions(s).some((a) => /^(secretsmanager|dynamodb):/.test(a));
        if (scoped) expect(resource(s)).not.toBe('"*"');
      }
    }
  });

  it("never gives the table to the token refresh function", () => {
    const tableActions = (fn: string) =>
      statementsFor(`${fn}ServiceRole`)
        .filter((s) => resource(s).includes("Table"))
        .flatMap(actions);
    expect(tableActions("HttpFunction")).toEqual(
      expect.arrayContaining(["dynamodb:PutItem", "dynamodb:Query", "dynamodb:BatchWriteItem"]),
    );
    expect(tableActions("TokenRefreshFunction")).toEqual([]);
  });
});
