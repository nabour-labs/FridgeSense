import { Stack, type StackProps } from "aws-cdk-lib";
import type { Construct } from "constructs";

export class FridgeSenseStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);
  }
}
