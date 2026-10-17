import { Duration, RemovalPolicy, Stack } from "aws-cdk-lib";
import type { Table } from "aws-cdk-lib/aws-dynamodb";
import { PolicyStatement } from "aws-cdk-lib/aws-iam";
import { Architecture, type Code, Function as LambdaFn, Runtime } from "aws-cdk-lib/aws-lambda";
import type { LogGroup } from "aws-cdk-lib/aws-logs";
import { BlockPublicAccess, Bucket, BucketEncryption, HttpMethods } from "aws-cdk-lib/aws-s3";
import type { ISecret } from "aws-cdk-lib/aws-secretsmanager";
import {
  Choice,
  Condition,
  DefinitionBody,
  Fail,
  JsonPath,
  LogLevel,
  StateMachine,
  StateMachineType,
  Succeed,
  TaskInput,
  Wait,
  WaitTime,
} from "aws-cdk-lib/aws-stepfunctions";
import { LambdaInvoke } from "aws-cdk-lib/aws-stepfunctions-tasks";
import { LogGroup as SfnLogGroup, RetentionDays } from "aws-cdk-lib/aws-logs";
import { Construct } from "constructs";

export interface DoorPipelineProps {
  code: Code;
  baseEnvironment: Record<string, string>;
  table: Table;
  appSecret: ISecret;
  tokenSecret: ISecret;
  logGroup: (id: string) => LogGroup;
  /** Door-check zones, `x,y,w,h;x,y,w,h` fractions of the uncropped still. */
  doorZones: string;
  /** Share of colourful pixels in a zone that counts as an opening. */
  doorThreshold: string;
  /** Crop for stored and analyzed stills (`x,y,w,h`); empty keeps the full frame. */
  stillCrop: string;
  /** Milliseconds between stills across a motion window (4 to 30 stills per event). */
  stillIntervalMs: string;
  /** Milliseconds between clip frames the door check looks at (the clip path). */
  doorFrameIntervalMs: string;
  novaModelId: string;
  novaPriceIn: string;
  novaPriceOut: string;
  novaPriceCacheRead: string;
  novaPriceCacheWrite: string;
  /** "true" adds Bedrock cache points to the analysis request. */
  novaCacheAnalysis: string;
  /** "false" stops debug traces (raw stills, scores, Nova requests) under each event's debug/. */
  debugTraces: string;
  /** IANA zone for the household day in usage totals. */
  timeZone: string;
  faceDetectPrice: string;
}

/** ARNs a Bedrock model ID may route to: a `us.` profile fans out to three US regions. */
export function bedrockResources(stack: Stack, modelId: string): string[] {
  if (modelId.startsWith("us.")) {
    const model = modelId.slice(3);
    return [
      `arn:aws:bedrock:${stack.region}:${stack.account}:inference-profile/${modelId}`,
      ...["us-east-1", "us-east-2", "us-west-2"].map(
        (r) => `arn:aws:bedrock:${r}::foundation-model/${model}`,
      ),
    ];
  }
  return [`arn:aws:bedrock:${stack.region}::foundation-model/${modelId}`];
}

/** Motion event → window → stills → door check → Nova → inventory, as a Step Functions workflow. */
export class DoorPipeline extends Construct {
  readonly stateMachine: StateMachine;
  readonly bucket: Bucket;

  constructor(scope: Construct, id: string, props: DoorPipelineProps) {
    super(scope, id);
    const stack = Stack.of(this);

    this.bucket = new Bucket(this, "Stills", {
      bucketName: `fridgesense-stills-${stack.account}`,
      blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
      encryption: BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      lifecycleRules: [{ expiration: Duration.days(7) }],
      // The app draws clip frames onto a canvas, which needs CORS. Any origin: reads still need a
      // presigned link, and naming the CloudFront domain here would make a dependency cycle.
      cors: [
        {
          allowedMethods: [HttpMethods.GET, HttpMethods.HEAD],
          allowedOrigins: ["*"],
          allowedHeaders: ["Range"],
          exposedHeaders: ["Content-Length", "Content-Range", "Accept-Ranges"],
        },
      ],
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    const fn = new LambdaFn(this, "PipelineFunction", {
      code: props.code,
      handler: "fridgesense.handlers.pipeline.handler",
      runtime: Runtime.PYTHON_3_13,
      architecture: Architecture.ARM_64,
      // Decodes the event clip for the door check: CPU scales with memory (2048 MB ~ 1.2 vCPU)
      memorySize: 2048,
      timeout: Duration.seconds(150),
      logGroup: props.logGroup("PipelineFunction"),
      description: "Door-event workflow steps: window, stills, door check, Nova, inventory",
      environment: {
        ...props.baseEnvironment,
        STILLS_BUCKET: this.bucket.bucketName,
        DOOR_ZONES: props.doorZones,
        DOOR_THRESHOLD: props.doorThreshold,
        STILL_CROP: props.stillCrop,
        STILL_INTERVAL_MS: props.stillIntervalMs,
        DOOR_FRAME_INTERVAL_MS: props.doorFrameIntervalMs,
        NOVA_MODEL_ID: props.novaModelId,
        NOVA_PRICE_IN: props.novaPriceIn,
        NOVA_PRICE_OUT: props.novaPriceOut,
        NOVA_PRICE_CACHE_READ: props.novaPriceCacheRead,
        NOVA_PRICE_CACHE_WRITE: props.novaPriceCacheWrite,
        NOVA_CACHE_ANALYSIS: props.novaCacheAnalysis,
        TIME_ZONE: props.timeZone,
        FACE_DETECT_PRICE: props.faceDetectPrice,
        DEBUG_TRACES: props.debugTraces,
      },
    });
    this.bucket.grantReadWrite(fn);
    props.table.grantReadWriteData(fn);
    props.appSecret.grantRead(fn);
    props.tokenSecret.grantRead(fn);
    props.tokenSecret.grantWrite(fn); // a token refresh during a run rotates the tokens
    fn.addToRolePolicy(
      new PolicyStatement({
        actions: ["bedrock:InvokeModel"],
        resources: bedrockResources(stack, props.novaModelId),
      }),
    );
    // Faces in stills are blurred before storage. DetectFaces has no resource-level scoping.
    fn.addToRolePolicy(
      new PolicyStatement({ actions: ["rekognition:DetectFaces"], resources: ["*"] }),
    );

    const step = (name: string, task: string) =>
      new LambdaInvoke(this, name, {
        lambdaFunction: fn,
        payload: TaskInput.fromObject({ task, input: JsonPath.entirePayload }),
        payloadResponseOnly: true,
      });

    const findWindow = step("FindWindow", "find_window");
    const fetchStills = step("FetchStills", "fetch_stills");
    const analyze = step("Analyze", "analyze");
    const save = step("Save", "save");
    const markFailed = step("MarkFailed", "mark_failed");
    const done = new Succeed(this, "Done");

    analyze.addRetry({
      errors: ["BedrockRetryable"],
      interval: Duration.seconds(5),
      maxAttempts: 2,
      backoffRate: 2,
    });
    analyze.addCatch(markFailed, { errors: ["States.ALL"], resultPath: "$.error" });
    // The event is already "analyzing" here; a failed save must not leave it there.
    save.addCatch(markFailed, { errors: ["States.ALL"], resultPath: "$.error" });
    // Window and stills only read Ring and overwrite the same keys, so a retry is safe.
    for (const s of [findWindow, fetchStills]) {
      s.addRetry({
        errors: ["States.TaskFailed"],
        interval: Duration.seconds(10),
        maxAttempts: 2,
        backoffRate: 2,
      });
      s.addCatch(markFailed, { errors: ["States.ALL"], resultPath: "$.error" });
    }
    // A Fail state, so ExecutionsFailed (and its alarm) counts these runs.
    markFailed.next(new Fail(this, "AnalysisFailed", { error: "AnalysisFailed" }));

    const waitAgain = new Wait(this, "WaitForRecordingEnd", {
      time: WaitTime.duration(Duration.seconds(20)),
    }).next(findWindow);

    const definition = new Wait(this, "WaitForRecording", {
      time: WaitTime.duration(Duration.seconds(20)),
    })
      .next(findWindow)
      .next(
        new Choice(this, "WindowReady")
          .when(Condition.stringEquals("$.window.status", "ready"), fetchStills)
          .otherwise(waitAgain),
      );
    fetchStills.next(
      new Choice(this, "IsDoorOpening")
        .when(Condition.stringEquals("$.outcome", "door_open"), analyze.next(save).next(done))
        .otherwise(new Succeed(this, "NoAnalysis")),
    );

    this.stateMachine = new StateMachine(this, "DoorEvents", {
      stateMachineName: "fridgesense-door-events",
      stateMachineType: StateMachineType.STANDARD,
      definitionBody: DefinitionBody.fromChainable(definition),
      timeout: Duration.minutes(15),
      logs: {
        destination: new SfnLogGroup(this, "DoorEventsLogs", {
          retention: RetentionDays.TWO_WEEKS,
          removalPolicy: RemovalPolicy.DESTROY,
        }),
        level: LogLevel.ERROR,
      },
    });
  }
}
