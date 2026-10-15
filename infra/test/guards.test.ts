import { readFileSync } from "node:fs";
import type { Template } from "aws-cdk-lib/assertions";
import { beforeAll, describe, expect, it } from "vitest";
import { ALERT_EMAIL, synthTemplate } from "./helpers.js";

let template: Template;

beforeAll(() => {
  template = synthTemplate();
});

type Resource = { Properties: Record<string, unknown>; DependsOn?: string[] };

function resourcesOf(type: string): Record<string, Resource> {
  return template.findResources(type) as Record<string, Resource>;
}

function defaultStage(): Resource {
  const stages = Object.values(resourcesOf("AWS::ApiGatewayV2::Stage")).filter(
    (s) => s.Properties.StageName === "$default",
  );
  expect(stages).toHaveLength(1);
  return stages[0];
}

function routeId(routeKey: string): string {
  const found = Object.entries(resourcesOf("AWS::ApiGatewayV2::Route")).filter(
    ([, r]) => r.Properties.RouteKey === routeKey,
  );
  expect(found).toHaveLength(1);
  return found[0][0];
}

describe("API throttling", () => {
  // Default stage throttled
  it("limits every route to 10 requests/s with a burst of 20", () => {
    expect(defaultStage().Properties.DefaultRouteSettings).toEqual({
      ThrottlingRateLimit: 10,
      ThrottlingBurstLimit: 20,
    });
  });

  // Passcode routes throttled
  it("limits the passcode routes to 1 request/s with a burst of 3", () => {
    const tight = { ThrottlingRateLimit: 1, ThrottlingBurstLimit: 3 };
    expect(defaultStage().Properties.RouteSettings).toEqual({
      "POST /api/session": tight,
      "POST /ring/link": tight,
    });
  });

  // Session route reaches the app API
  it("gives POST /api/session its own route on the app API integration", () => {
    const routes = resourcesOf("AWS::ApiGatewayV2::Route");
    const session = routes[routeId("POST /api/session")].Properties.Target;
    const proxy = routes[routeId("ANY /api/{proxy+}")].Properties.Target;
    expect(session).toEqual(proxy);
  });

  // Routes exist before their limits
  it("creates the passcode routes before the stage", () => {
    const deps = defaultStage().DependsOn ?? [];
    expect(deps).toEqual(
      expect.arrayContaining([routeId("POST /api/session"), routeId("POST /ring/link")]),
    );
  });
});

describe("cost and failure alerts", () => {
  // Budget at 80 percent
  it("emails at 80% of a $20 monthly cost budget", () => {
    template.resourceCountIs("AWS::Budgets::Budget", 1);
    template.hasResourceProperties("AWS::Budgets::Budget", {
      Budget: {
        BudgetType: "COST",
        TimeUnit: "MONTHLY",
        BudgetLimit: { Amount: 20, Unit: "USD" },
      },
      NotificationsWithSubscribers: [
        {
          Notification: {
            NotificationType: "ACTUAL",
            ComparisonOperator: "GREATER_THAN",
            Threshold: 80,
            ThresholdType: "PERCENTAGE",
          },
          Subscribers: [{ SubscriptionType: "EMAIL", Address: ALERT_EMAIL }],
        },
      ],
    });
  });

  // Alarm on failed executions
  it("alarms on any failed door-event execution and emails through SNS", () => {
    const machines = Object.entries(resourcesOf("AWS::StepFunctions::StateMachine")).filter(
      ([, r]) => r.Properties.StateMachineName === "fridgesense-door-events",
    );
    expect(machines).toHaveLength(1);
    const [machineId] = machines[0];
    const topics = Object.keys(resourcesOf("AWS::SNS::Topic"));
    expect(topics).toHaveLength(1);
    template.hasResourceProperties("AWS::SNS::Subscription", {
      Protocol: "email",
      Endpoint: ALERT_EMAIL,
      TopicArn: { Ref: topics[0] },
    });
    template.hasResourceProperties("AWS::CloudWatch::Alarm", {
      Namespace: "AWS/States",
      MetricName: "ExecutionsFailed",
      Dimensions: [{ Name: "StateMachineArn", Value: { Ref: machineId } }],
      Statistic: "Sum",
      Period: 300,
      Threshold: 1,
      ComparisonOperator: "GreaterThanOrEqualToThreshold",
      EvaluationPeriods: 1,
      TreatMissingData: "notBreaching",
      AlarmActions: [{ Ref: topics[0] }],
    });
  });

  // Address missing
  it.each([
    ["missing", undefined],
    ["empty", ""],
  ])("refuses to synthesize when the alert email is %s", (_, alertEmail) => {
    expect(() => synthTemplate({ alertEmail } as Record<string, string>)).toThrow(/alertEmail/);
  });

  it("keeps any email address out of the stack source", () => {
    const src = readFileSync(new URL("../lib/fridgesense-stack.ts", import.meta.url), "utf8");
    expect(src).not.toMatch(/"[^"\s]+@[^"\s]+"/);
  });
});
