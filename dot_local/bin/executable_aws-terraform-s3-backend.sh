#!/usr/bin/env bash

script_dir=$(cd "$(dirname $0)" || exit; pwd -P)

region=us-west-2
account=240259995564

usage() {
    echo "${script_dir}: Creates an S3 bucket and DynamoDB table suitable for a terraform remote backend"
    echo "Usage: ${0##*/} [flags] <parameter1> <parameter2> ..."
    echo "  -h             Print usage instructions"
    echo "  -a ACCOUNT_ID  AWS account ID where ECR is located (default: ${account})"
    echo "  -r AWS_REGION  AWS region where ECR is located (default: ${region})"
}

param() {
  if [ -z "$1" ]; then
    echo "Missing parameter: $2"
    exit 1
  else
    echo $1
  fi
}

while getopts ":ha:r:" opt; do
    case $opt in
    h)
        usage
        exit 0
        ;;
    a)
        account=$OPTARG
        ;;
    r)
        region=$OPTARG
        ;;
    \?)
        echo "Invalid option: -$opt" >&2
        exit 1
        ;;
    :)
        echo "Option -$opt requires an argument." >&2
        exit 1
        ;;
    esac
done
shift $(($OPTIND - 1))

bucket=$(param $1 "Please specify a name for the S3 bucket.")
db=$(param $1 "Please specify a name for the Dynamo DB.")

echo "Creating S3 bucket..."
echo aws s3api create-bucket --bucket ${bucket} --region ${region} --create-bucket-configuration LocationConstraint=${region}
echo "Enabling S3 bucket versioning..."
echo aws s3api put-bucket-versioning --bucket ${bucket} --region ${region} --versioning-configuration Status=Enabled
echo "Creating DynamoDB table..."
echo aws dynamodb create-table \
    --table-name ${db} \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST

echo "Add the following to your terraform configuration to use this bucket:"
cat <<EOF
terraform {
  backend "s3" {
    bucket         = "${bucket}"
    key            = "terraform.tfstate"
    region         = "${region}"
    dynamodb_table = "${db}"
    encrypt        = true
  }
}
EOF
