#!/usr/bin/env node
import { App } from "aws-cdk-lib";
import { FridgeSenseStack } from "../lib/fridgesense-stack.js";

const app = new App();
new FridgeSenseStack(app, "FridgeSense", {
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: "us-east-1" },
});
