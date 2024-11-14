# Define the provider
provider "aws" {
  region = "eu-central-1"

  default_tags {
    tags = {
      "mkosinski" = "true"
    }
  }
}

# Variable for name prefix
variable "name_prefix" {
  default = "clurgo-workshop"
}

variable "usernames" {
  type = list(string)
  default = [
    "aws-bartlomiej",
    #     "aws-dominik",
    #     "aws-krzysztof",
    #     "aws-lukasz",
    #     "aws-maciej",
    #     "aws-michal"
  ]
}

# IAM Users
resource "aws_iam_user" "this" {
  for_each = toset(var.usernames)
  name = each.value
}

# IAM User Login Profiles for Console Access
resource "aws_iam_user_login_profile" "this" {
  for_each = toset(var.usernames)
  user = aws_iam_user.this[each.key].name

  password_reset_required = false
}


# IAM User Groups
resource "aws_iam_group" "cloud9" {
  name = "${var.name_prefix}-cloud9"
}

resource "aws_iam_group" "services_base" {
  name = "${var.name_prefix}-services-base"
}

resource "aws_iam_group" "services_supporting" {
  name = "${var.name_prefix}-services-supporting"
}

# Attach IAM policies to the Cloud9 group
resource "aws_iam_group_policy_attachment" "cloud9_policies" {
  for_each = toset([
    "AWSCloud9EnvironmentMember",
    "AWSCloud9User"
  ])
  group      = aws_iam_group.cloud9.name
  policy_arn = "arn:aws:iam::aws:policy/${each.key}"
}

resource "aws_iam_group_policy_attachment" "services_policies_base" {
  for_each = toset([
    "AmazonEC2FullAccess",
    "AmazonECS_FullAccess",
    "AmazonRDSFullAccess",
    "AmazonS3FullAccess",
    "AmazonSNSFullAccess",
    "AmazonSQSFullAccess",
    "AmazonTextractFullAccess"
  ])
  group      = aws_iam_group.services_base.name
  policy_arn = "arn:aws:iam::aws:policy/${each.key}"
}

resource "aws_iam_group_policy_attachment" "services_policies_supporting" {
  for_each = toset([
    "AWSCloudShellFullAccess",
    "CloudWatchFullAccessV2",
    "ReadOnlyAccess"
  ])
  group      = aws_iam_group.services_supporting.name
  policy_arn = "arn:aws:iam::aws:policy/${each.key}"
}

# Attach users to groups
resource "aws_iam_group_membership" "cloud9" {
  name  = "${var.name_prefix}-cloud9-members"
  users = [for u in aws_iam_user.this : u.name]
  group = aws_iam_group.cloud9.name
}

resource "aws_iam_group_membership" "services_base" {
  name  = "${var.name_prefix}-services-base-members"
  users = [for u in aws_iam_user.this : u.name]
  group = aws_iam_group.services_base.name
}

resource "aws_iam_group_membership" "services_supporting" {
  name  = "${var.name_prefix}-services-members"
  users = [for u in aws_iam_user.this : u.name]
  group = aws_iam_group.services_supporting.name
}

# Data sources to get existing VPC and Subnet by name
data "aws_vpc" "this" {
  filter {
    name = "tag:Name"
    values = ["clurgo-workshop-vpc"]
  }
}

data "aws_subnet" "this" {
  filter {
    name = "tag:Name"
    values = ["clurgo-workshop-subnet-public1-eu-central-1a"]
  }
  vpc_id = data.aws_vpc.this.id
}

data "aws_subnets" "this" {
  filter {
    name = "tag:Name"
    values = [
      "clurgo-workshop-subnet-public1-eu-central-1a",
      "clurgo-workshop-subnet-public2-eu-central-1b"
    ]
  }

  filter {
    name = "vpc-id"
    values = [data.aws_vpc.this.id]
  }
}


# Cloud9 Environment for each user
resource "aws_cloud9_environment_ec2" "this" {
  for_each = toset(var.usernames)
  name          = "${each.value}-cloud9-env"
  instance_type = "m5.large"
  automatic_stop_time_minutes = 2880 # 2 days in minutes
  subnet_id     = data.aws_subnet.this.id
  image_id      = "amazonlinux-2023-x86_64"
  owner_arn     = aws_iam_user.this[each.key].arn
}