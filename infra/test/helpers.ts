import { App } from "aws-cdk-lib";
import { Template } from "aws-cdk-lib/assertions";
import { FridgeSenseStack } from "../lib/fridgesense-stack.js";

export const ALERT_EMAIL = "owner@example.test";

// Bundling is disabled so tests don't need uv or the backend build.
export function synthTemplate(context: Record<string, string> = {}): Template {
  const app = new App({
    context: { "aws:cdk:bundling-stacks": [], alertEmail: ALERT_EMAIL, ...context },
  });
  const stack = new FridgeSenseStack(app, "Test", { env: { region: "us-east-1" } });
  return Template.fromStack(stack);
}
