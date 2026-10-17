import type { Template } from "aws-cdk-lib/assertions";
import { beforeAll, describe, expect, it } from "vitest";
import { synthTemplate } from "./helpers.js";

let template: Template;

type Resource = { Properties: Record<string, unknown>; DeletionPolicy?: string };
type Statement = { Action: string | string[]; Resource: unknown; Effect: string };
type State = Record<string, unknown> & { Type: string; Next?: string; End?: boolean };

beforeAll(() => {
  template = synthTemplate();
});

function resourcesOf(type: string): Record<string, Resource> {
  return template.findResources(type) as Record<string, Resource>;
}

function lambdaByHandler(handler: string): [string, Resource] {
  const found = Object.entries(resourcesOf("AWS::Lambda::Function")).filter(
    ([, r]) => r.Properties.Handler === handler,
  );
  expect(found).toHaveLength(1);
  return found[0];
}

function statementsFor(roleIdPrefix: string): Statement[] {
  return Object.values(resourcesOf("AWS::IAM::Policy"))
    .filter((p) => JSON.stringify(p.Properties.Roles).includes(roleIdPrefix))
    .flatMap((p) => (p.Properties.PolicyDocument as { Statement: Statement[] }).Statement);
}

const actions = (s: Statement) => [s.Action].flat();

/** The state machine definition with CloudFormation tokens replaced by placeholders. */
function definition(): { StartAt: string; States: Record<string, State> } {
  const [sm] = Object.values(resourcesOf("AWS::StepFunctions::StateMachine"));
  const def = sm.Properties.DefinitionString as { "Fn::Join": [string, unknown[]] } | string;
  const text =
    typeof def === "string"
      ? def
      : def["Fn::Join"][1].map((p) => (typeof p === "string" ? p : "TOKEN")).join("");
  return JSON.parse(text);
}

describe("door-event state machine", () => {
  it("is a Standard workflow", () => {
    const [sm] = Object.values(resourcesOf("AWS::StepFunctions::StateMachine"));
    expect(sm.Properties.StateMachineType ?? "STANDARD").toBe("STANDARD");
  });

  it("waits 20 s, then finds the window, looping every 20 s while pending", () => {
    const { StartAt, States } = definition();
    expect(States[StartAt]).toMatchObject({ Type: "Wait", Seconds: 20, Next: "FindWindow" });
    expect(States.FindWindow).toMatchObject({ Type: "Task", Next: "WindowReady" });
    const choice = States.WindowReady as State & {
      Choices: { Variable: string; StringEquals: string; Next: string }[];
      Default: string;
    };
    expect(choice.Choices).toEqual([
      { Variable: "$.window.status", StringEquals: "ready", Next: "FetchStills" },
    ]);
    expect(States[choice.Default]).toMatchObject({ Type: "Wait", Seconds: 20, Next: "FindWindow" });
  });

  it("only analyzes door openings", () => {
    const { States } = definition();
    expect(States.FetchStills).toMatchObject({ Type: "Task", Next: "IsDoorOpening" });
    const choice = States.IsDoorOpening as State & {
      Choices: { Variable: string; StringEquals: string; Next: string }[];
      Default: string;
    };
    expect(choice.Choices).toEqual([
      { Variable: "$.outcome", StringEquals: "door_open", Next: "Analyze" },
    ]);
    expect(States[choice.Default].Type).toBe("Succeed");
  });

  it("retries Analyze on BedrockRetryable and marks the event failed otherwise", () => {
    const { States } = definition();
    const analyze = States.Analyze as State & {
      Retry: Record<string, unknown>[];
      Catch: Record<string, unknown>[];
    };
    expect(analyze.Next).toBe("Save");
    expect(analyze.Retry).toContainEqual(
      expect.objectContaining({
        ErrorEquals: ["BedrockRetryable"],
        IntervalSeconds: 5,
        MaxAttempts: 2,
        BackoffRate: 2,
      }),
    );
    expect(analyze.Catch).toEqual([
      { ErrorEquals: ["States.ALL"], ResultPath: "$.error", Next: "MarkFailed" },
    ]);
    expect(States.MarkFailed.Type).toBe("Task");
    expect(States.Save.Type).toBe("Task");
  });

  it("save fails: marks the event failed instead of leaving it analyzing", () => {
    const { States } = definition();
    const save = States.Save as State & { Catch?: Record<string, unknown>[] };
    expect(save.Catch).toEqual([
      { ErrorEquals: ["States.ALL"], ResultPath: "$.error", Next: "MarkFailed" },
    ]);
  });

  it("passes the task name and the run state to the pipeline Lambda", () => {
    const { States } = definition();
    const tasks = { FindWindow: "find_window", FetchStills: "fetch_stills", Analyze: "analyze",
      Save: "save", MarkFailed: "mark_failed" };
    for (const [state, task] of Object.entries(tasks)) {
      expect(States[state].Parameters).toEqual({ task, "input.$": "$" });
    }
  });
});

describe("pipeline Lambda", () => {
  it("is arm64 with 2048 MB, 150 s (clip decoding) and the pipeline settings", () => {
    const [, fn] = lambdaByHandler("fridgesense.handlers.pipeline.handler");
    expect(fn.Properties.Runtime).toBe("python3.13");
    expect(fn.Properties.Architectures).toEqual(["arm64"]);
    expect(fn.Properties.MemorySize).toBe(2048);
    expect(fn.Properties.Timeout).toBe(150);
    const vars = (fn.Properties.Environment as { Variables: Record<string, unknown> }).Variables;
    expect(Object.keys(vars).sort()).toEqual([
      "DEBUG_TRACES",
      "DOOR_FRAME_INTERVAL_MS",
      "DOOR_THRESHOLD",
      "DOOR_ZONES",
      "FACE_DETECT_PRICE",
      "NOVA_CACHE_ANALYSIS",
      "NOVA_MODEL_ID",
      "NOVA_PRICE_CACHE_READ",
      "NOVA_PRICE_CACHE_WRITE",
      "NOVA_PRICE_IN",
      "NOVA_PRICE_OUT",
      "RING_APP_SECRET_ID",
      "RING_TOKENS_SECRET_ID",
      "STILLS_BUCKET",
      "STILL_CROP",
      "STILL_INTERVAL_MS",
      "TABLE_NAME",
      "TIME_ZONE",
    ]);
    expect(vars.NOVA_MODEL_ID).toBe("us.amazon.nova-2-lite-v1:0");
    expect(vars.NOVA_PRICE_CACHE_READ).toBe("0.0000825");
    expect(vars.NOVA_PRICE_CACHE_WRITE).toBe("0");
    expect(vars.NOVA_CACHE_ANALYSIS).toBe("false");
    expect(vars.TIME_ZONE).toBe("America/Toronto");
    expect(vars.DOOR_ZONES).toBe("0.38,0.32,0.21,0.30;0.455,0.60,0.12,0.18");
    expect(vars.DOOR_THRESHOLD).toBe("0.01");
    expect(vars.STILL_CROP).toBe("0.30,0.0,0.34,1.0");
    expect(vars.STILL_INTERVAL_MS).toBe("1000");
    expect(vars.DOOR_FRAME_INTERVAL_MS).toBe("500");
    expect(vars).not.toHaveProperty("DOOR_BOX");
    expect(vars.FACE_DETECT_PRICE).toBe("0.001");
    // Off by default when deployed
    expect(vars.DEBUG_TRACES).toBe("false");
  });

  it("may call only rekognition:DetectFaces, on *", () => {
    const [id] = lambdaByHandler("fridgesense.handlers.pipeline.handler");
    const rekognition = statementsFor(id.replace(/[A-F0-9]{8}$/, "")).filter((s) =>
      actions(s).some((a) => a.startsWith("rekognition:")),
    );
    expect(rekognition.flatMap(actions)).toEqual(["rekognition:DetectFaces"]);
    expect(rekognition.map((s) => s.Resource)).toEqual(["*"]);
  });

  it("may invoke only the Nova 2 Lite profile and its regional models", () => {
    const [id] = lambdaByHandler("fridgesense.handlers.pipeline.handler");
    const bedrock = statementsFor(id.replace(/[A-F0-9]{8}$/, "")).filter((s) =>
      actions(s).some((a) => a.startsWith("bedrock:")),
    );
    expect(bedrock.flatMap(actions)).toEqual(["bedrock:InvokeModel"]);
    const resources = JSON.stringify(bedrock.map((s) => s.Resource));
    expect(resources).toContain("inference-profile/us.amazon.nova-2-lite-v1:0");
    for (const region of ["us-east-1", "us-east-2", "us-west-2"]) {
      expect(resources).toContain(`arn:aws:bedrock:${region}::foundation-model/amazon.nova-2-lite-v1:0`);
    }
    expect(resources).not.toContain('"*"');
  });
});

describe("stills bucket", () => {
  it("Stills deleted after 7 days; bucket private and encrypted", () => {
    template.hasResourceProperties("AWS::S3::Bucket", {
      LifecycleConfiguration: {
        Rules: [{ ExpirationInDays: 7, Status: "Enabled" }],
      },
      PublicAccessBlockConfiguration: {
        BlockPublicAcls: true,
        BlockPublicPolicy: true,
        IgnorePublicAcls: true,
        RestrictPublicBuckets: true,
      },
      BucketEncryption: {
        ServerSideEncryptionConfiguration: [
          { ServerSideEncryptionByDefault: { SSEAlgorithm: "AES256" } },
        ],
      },
    });
  });

  it("enforces SSL", () => {
    const policies = JSON.stringify(resourcesOf("AWS::S3::BucketPolicy"));
    expect(policies).toContain("aws:SecureTransport");
  });
});

describe("webhook hand-over", () => {
  it("gives the HTTP Lambda the state machine ARN and only StartExecution on it", () => {
    const [id, fn] = lambdaByHandler("fridgesense.handlers.http.handler");
    const vars = (fn.Properties.Environment as { Variables: Record<string, unknown> }).Variables;
    expect(vars.STATE_MACHINE_ARN).toBeDefined();
    const states = statementsFor(id.replace(/[A-F0-9]{8}$/, "")).filter((s) =>
      actions(s).some((a) => a.startsWith("states:")),
    );
    expect(states.flatMap(actions)).toEqual(["states:StartExecution"]);
    expect(JSON.stringify(states.map((s) => s.Resource))).toContain("DoorEvents");
  });
});

describe("logs", () => {
  it("use fixed log group names so the README commands work", () => {
    const names = Object.values(resourcesOf("AWS::Logs::LogGroup"))
      .map((g) => g.Properties.LogGroupName)
      .filter((n) => typeof n === "string")
      .sort();
    expect(names).toEqual([
      "/fridgesense/api",
      "/fridgesense/http",
      "/fridgesense/mcp",
      "/fridgesense/pipeline",
      "/fridgesense/token-refresh",
    ]);
  });
});
