# The BlurClip Lambda: deface (CenterFace on onnxruntime) + PyAV, for arm64.
FROM public.ecr.aws/lambda/python:3.13-arm64

# requirements.txt is `uv export --frozen --no-dev --no-emit-project --no-hashes`: deface's
# opencv-python (needs libGL) is overridden away in favour of opencv-python-headless.
COPY requirements.txt .
# --no-deps: requirements.txt pins every package; without it pip pulls deface's opencv-python back in.
RUN pip install --no-cache-dir --no-deps -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

COPY src/clipblur "${LAMBDA_TASK_ROOT}/clipblur"

CMD ["clipblur.handler.handler"]
