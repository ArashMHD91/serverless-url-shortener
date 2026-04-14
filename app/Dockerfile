FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.12

COPY main.py ${LAMBDA_TASK_ROOT}

RUN pip install boto3

CMD ["main.handler"]