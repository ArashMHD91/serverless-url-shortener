# Serverless URL Shortener on AWS

A fully serverless URL shortener REST API built with AWS Lambda, API Gateway, and DynamoDB. All infrastructure is provisioned with Terraform and deployed automatically via GitHub Actions CI/CD pipeline.

---

## Architecture

```
GitHub Push
    │
    ▼
GitHub Actions
    ├── Build Docker image (linux/amd64)
    ├── Push to Amazon ECR
    ├── Update Lambda function
    └── Terraform Apply
            │
            ▼
API Gateway (HTTP API)
    │
    ▼
AWS Lambda (Container Image)
    │
    ▼
Amazon DynamoDB
```

---

## Features

- `POST /shorten` — takes a long URL and returns a short code
- `GET /{code}` — redirects to the original URL (301)
- `DELETE /{code}` — deletes a short URL
- Fully serverless, no EC2 or ECS required
- Container-based Lambda deployment via ECR
- Infrastructure as Code with Terraform
- Remote Terraform state stored in S3
- Automated CI/CD with GitHub Actions on every push to main

---

## Tech Stack

| Layer | Technology |
|---|---|
| Compute | AWS Lambda (Container Image) |
| API | Amazon API Gateway HTTP API |
| Database | Amazon DynamoDB (PAY_PER_REQUEST) |
| Registry | Amazon ECR |
| IaC | Terraform |
| CI/CD | GitHub Actions |
| Language | Python 3.12 |

---

## Project Structure

```
serverless-url-shortener/
├── app/
│   ├── main.py           # Lambda handler
│   └── Dockerfile        # Container image definition
├── terraform/
│   ├── main.tf           # Provider and S3 backend
│   ├── variables.tf      # Input variables
│   ├── ecr.tf            # ECR repository
│   ├── dynamodb.tf       # DynamoDB table
│   ├── lambda.tf         # Lambda function and IAM role
│   └── api_gateway.tf    # API Gateway HTTP API
└── .github/
    └── workflows/
        └── deploy.yml    # CI/CD pipeline
```

---

## Prerequisites

Before you start, make sure you have the following installed and configured:

- An AWS account with admin or sufficient IAM permissions
- [Terraform >= 1.0](https://developer.hashicorp.com/terraform/install)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) configured with your credentials
- A GitHub repository with Actions enabled

---

## Deployment Guide

### Step 1: Clone the repository

```bash
git clone https://github.com/ArashMHD91/serverless-url-shortener.git
cd serverless-url-shortener
```

### Step 2: Create an S3 bucket for Terraform remote state

Replace `<your-account-id>` with your AWS account ID.

```bash
aws s3 mb s3://url-shortener-tfstate-<your-account-id> --region eu-central-1
```

Then update the bucket name in `terraform/main.tf`:

```hcl
backend "s3" {
  bucket = "url-shortener-tfstate-<your-account-id>"
  key    = "terraform.tfstate"
  region = "eu-central-1"
}
```

### Step 3: Create an IAM user for GitHub Actions

Go to **AWS Console → IAM → Users → Create User** with the following settings:

- Username: `github-actions-url-shortener`
- Access type: Programmatic only (no console access)

Attach these managed policies:

- `AmazonEC2ContainerRegistryFullAccess`
- `AWSLambda_FullAccess`
- `AmazonDynamoDBFullAccess`
- `IAMFullAccess`
- `AmazonAPIGatewayAdministrator`
- `AmazonS3FullAccess`

After creating the user, go to **Security credentials → Create access key** and save the `Access Key ID` and `Secret Access Key`.

### Step 4: Add GitHub Secrets

In your GitHub repo go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | Your IAM user access key ID |
| `AWS_SECRET_ACCESS_KEY` | Your IAM user secret access key |

### Step 5: Bootstrap — push the first Docker image manually

On the very first deployment, the Docker image must exist in ECR before Terraform can create the Lambda function. This is a one-time step.

First, configure your local AWS CLI with the IAM user credentials:

```bash
aws configure
```

Then initialize Terraform and create the ECR repository:

```bash
cd terraform
terraform init
terraform apply -target=aws_ecr_repository.lambda_repo
```

Type `yes` when prompted. Once ECR is created, build and push the image:

```bash
cd ..

aws ecr get-login-password --region eu-central-1 | \
  docker login --username AWS --password-stdin \
  <your-account-id>.dkr.ecr.eu-central-1.amazonaws.com

docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --push \
  -t <your-account-id>.dkr.ecr.eu-central-1.amazonaws.com/url-shortener:latest \
  ./app
```

> Why `--provenance=false`? Docker Desktop on Windows/Mac builds multi-platform manifest lists by default. AWS Lambda only accepts single-platform images, so this flag ensures a clean `linux/amd64` image is pushed.

### Step 6: Deploy everything

Push to main to trigger the full CI/CD pipeline:

```bash
git push origin main
```

GitHub Actions will:
1. Build and push the Docker image to ECR
2. Update the Lambda function with the new image
3. Run `terraform apply` to provision all remaining infrastructure

### Step 7: Get your API endpoint

After the pipeline finishes, go to **AWS Console → API Gateway** and copy your invoke URL, or run:

```bash
cd terraform
terraform output api_endpoint
```

---

## Usage

### Shorten a URL

```bash
curl -X POST https://<api-endpoint>/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.example.com"}'
```

Response:

```json
{"short_code": "qnEbFD", "url": "https://www.example.com"}
```

### Redirect to original URL

```bash
curl -v https://<api-endpoint>/qnEbFD
```

Returns a `301 Moved Permanently` with a `Location` header pointing to the original URL.

### Delete a short URL

```bash
curl -X DELETE https://<api-endpoint>/qnEbFD
```

Response:

```json
{"message": "deleted"}
```

---

## How it works

**Lambda handler (`app/main.py`)** receives all HTTP requests from API Gateway. It reads the HTTP method and path to decide which action to take, then reads from or writes to DynamoDB accordingly.

**DynamoDB** stores a simple key-value mapping: `short_code → original_url`. The table uses `PAY_PER_REQUEST` billing, meaning you only pay per read/write operation with no provisioned capacity needed.

**API Gateway HTTP API** sits in front of Lambda and routes the three HTTP methods to the same Lambda function. The Lambda function itself handles the routing internally.

**ECR** stores the Docker image. Lambda pulls the image directly from ECR at invocation time.

**Terraform remote state in S3** ensures that both your local machine and GitHub Actions always share the same infrastructure state, preventing conflicts and duplicate resource creation.

---

## Cleanup

To destroy all AWS resources and avoid any costs:

```bash
cd terraform
terraform destroy
```

Type `yes` when prompted.

> The ECR repository has `force_delete = true` set in Terraform, so all images are removed automatically before the repository is deleted.

Also delete the S3 state bucket manually if you no longer need it:

```bash
aws s3 rb s3://url-shortener-tfstate-<your-account-id> --force
```

---

## Author

**Arash** — [github.com/ArashMHD91](https://github.com/ArashMHD91)