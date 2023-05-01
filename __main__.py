from pulumi import export, ResourceOptions, Config
import pulumi_aws as aws
import pulumi
from pulumi_docker import Image, DockerBuildArgs, RegistryArgs
import json
import backend, frontend

config = Config()
tags = config.get_object("tags")
frontend_app_name = config.get("frontend_app", "infra-web")
backend_api_name = config.get("backend_api", "infra-api")

# Create an ECS cluster to run a container-based service.
cluster = aws.ecs.Cluster('cluster', tags=tags)

# Read back the default VPC and public subnets, which we will use.
default_vpc = aws.ec2.get_vpc(default=True)
default_vpc_subnets = aws.ec2.get_subnets(
	filters = [
		aws.ec2.GetSubnetsFilterArgs(
			name='vpc-id',
			values=[default_vpc.id],
		),
	],
)

# Create a SecurityGroup that permits HTTP ingress and unrestricted egress.
api_sec_group = aws.ec2.SecurityGroup('api-secgrp',
	vpc_id=default_vpc.id,
	description='Enable HTTP access',
	ingress=[aws.ec2.SecurityGroupIngressArgs(
		protocol='tcp',
		from_port=80,
		to_port=80,
		cidr_blocks=['0.0.0.0/0'],
	), aws.ec2.SecurityGroupIngressArgs(
		protocol='tcp',
		from_port=5000,
		to_port=5000,
		cidr_blocks=['0.0.0.0/0'],
	)],
  	egress=[aws.ec2.SecurityGroupEgressArgs(
		protocol='-1',
		from_port=0,
		to_port=0,
		cidr_blocks=['0.0.0.0/0'],
	)],
	tags=tags,
)

# Create an IAM role that can be used by our service's task.
role = aws.iam.Role('task-exec-role',
	assume_role_policy=json.dumps({
		'Version': '2008-10-17',
		'Statement': [{
			'Sid': '',
			'Effect': 'Allow',
			'Principal': {
				'Service': 'ecs-tasks.amazonaws.com'
			},
			'Action': 'sts:AssumeRole',
		}]
	}),
	tags=tags,
)

rpa = aws.iam.RolePolicyAttachment('task-exec-policy',
	role=role.name,
	policy_arn='arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy',
)

#Create backend service and its related assets
backend_api=backend.BackendService(backend_api_name, backend.BackendServiceArgs(
    vpc_id=default_vpc.id,
    subnet_ids=default_vpc_subnets.ids,
    security_group_ids=[api_sec_group.id],
	ecs_cluster=cluster,
	role=role,
	tags=tags
))

#Create frontend service and its related assets.
frontend_api=frontend.FrontendService(frontend_app_name,
	frontend.FrontendServiceArgs(
		backend_api=backend_api,
    	vpc_id=default_vpc.id,
    	subnet_ids=default_vpc_subnets.ids,
    	security_group_ids=[api_sec_group.id],
		ecs_cluster=cluster,
		role=role,
		tags=tags,
	),
	opts=ResourceOptions(depends_on=[backend_api]),
)

export('api_url', backend_api.api_alb.dns_name)
export('web_url', frontend_api.web_alb.dns_name)