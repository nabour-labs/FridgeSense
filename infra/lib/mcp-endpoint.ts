import { CfnOutput, Duration, Stack } from "aws-cdk-lib";
import { type HttpApi, HttpMethod } from "aws-cdk-lib/aws-apigatewayv2";
import { HttpLambdaIntegration } from "aws-cdk-lib/aws-apigatewayv2-integrations";
import type { Table } from "aws-cdk-lib/aws-dynamodb";
import { Rule, RuleTargetInput, Schedule } from "aws-cdk-lib/aws-events";
import { LambdaFunction } from "aws-cdk-lib/aws-events-targets";
import { Architecture, type Code, Function as LambdaFn, Runtime } from "aws-cdk-lib/aws-lambda";
import type { LogGroup } from "aws-cdk-lib/aws-logs";
import type { ISecret } from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";

export interface McpEndpointProps {
  api: HttpApi;
  code: Code;
  baseEnvironment: Record<string, string>;
  table: Table;
  appSecret: ISecret;
  tokenSecret: ISecret;
  logGroup: (id: string) => LogGroup;
  timeZone: string;
}

/** The read-only MCP server for Alexa+ and other MCP clients, at /mcp/{key}. */
export class McpEndpoint extends Construct {
  constructor(scope: Construct, id: string, props: McpEndpointProps) {
    super(scope, id);

    const fn = new LambdaFn(this, "McpFunction", {
      code: props.code,
      handler: "fridgesense.handlers.mcp.handler",
      runtime: Runtime.PYTHON_3_13,
      architecture: Architecture.ARM_64,
      // More memory means more CPU, so the MCP SDK imports faster on a cold start.
      memorySize: 512,
      timeout: Duration.seconds(10),
      logGroup: props.logGroup("McpFunction"),
      description: "Read-only MCP server: find_item, get_inventory, fridge_activity, last_opened",
      environment: { ...props.baseEnvironment, TIME_ZONE: props.timeZone },
    });
    props.table.grantReadData(fn);
    props.appSecret.grantRead(fn);
    props.tokenSecret.grantRead(fn);

    props.api.addRoutes({
      path: "/mcp/{key}",
      methods: [HttpMethod.ANY],
      integration: new HttpLambdaIntegration("McpIntegration", fn),
    });

    // Alexa+ expects tool round trips under 500 ms; keep one instance warm.
    new Rule(this, "WarmUp", {
      schedule: Schedule.rate(Duration.minutes(5)),
      targets: [new LambdaFunction(fn, { event: RuleTargetInput.fromObject({ warmup: true }) })],
    });

    new CfnOutput(Stack.of(this), "McpUrlTemplate", {
      value: `${props.api.apiEndpoint}/mcp/<mcp_key>`,
      description: "Replace <mcp_key> with the mcp_key in fridgesense/ring-app",
    });
  }
}
