import json

import pulumi_aws as aws
from pulumi import ComponentResource, Output, ResourceOptions
from pulumi_docker import Image, DockerBuildArgs, RegistryArgs
import json

class BackendServiceArgs:

    def __init__(self,
                 vpc_id=None,
                 subnet_ids=None,  # array of subnet IDs
                 security_group_ids=None,  # array of security group Ids
                 ecs_cluster=None,
                 role=None,
                 tags=None):
        self.vpc_id = vpc_id
        self.subnet_ids = subnet_ids
        self.security_group_ids = security_group_ids
        self.cluster = ecs_cluster
        self.role = role
        self.tags = tags

class BackendService(ComponentResource):

    def __init__(self,
                 name: str,
                 args: BackendServiceArgs,
                 opts: ResourceOptions = None):

        super().__init__('custom:resource:Backend', name, {}, opts)

        self.api_alb = aws.lb.LoadBalancer(f'{name}-lb',
	        internal=True,
	        security_groups=args.security_group_ids,
	        subnets=args.subnet_ids,
	        tags=args.tags,
            opts=ResourceOptions(parent=self)
        )

        api_atg = aws.lb.TargetGroup(f'{name}-tg',
	        port=5000,
	        protocol='HTTP',
	        target_type='ip',
	        vpc_id=args.vpc_id,
	        health_check=aws.lb.TargetGroupHealthCheckArgs(
		        path='/WeatherForecast'
	        ),
	        tags=args.tags,
            opts=ResourceOptions(parent=self)
        )

        api_lb_listener = aws.lb.Listener(f'{name}-listener',
	        load_balancer_arn=self.api_alb.arn,
	        port=80,
	        default_actions=[aws.lb.ListenerDefaultActionArgs(
		        type='forward',
		        target_group_arn=api_atg.arn,
	        )],
	        tags=args.tags,
            opts=ResourceOptions(parent=self)
        )

        backend_api_ecr_repository = aws.ecr.Repository(f'{name}-repository', 
            tags=args.tags, 
            image_tag_mutability="MUTABLE",
            opts=ResourceOptions(parent=self),
        )

        backend_ecr_auth_token = aws.ecr.get_authorization_token_output(
            registry_id=backend_api_ecr_repository.registry_id
        )

        #Building backend infra-api image and pushing to ECR.
        backend_api_image = Image(f'{name}-image',
            build=DockerBuildArgs(
                context="infra-api",
                dockerfile="infra-api/Dockerfile",
            ),
            image_name=backend_api_ecr_repository.repository_url,
            registry=RegistryArgs(
                username="AWS",
                password=Output.secret(backend_ecr_auth_token.password),
                server=backend_api_ecr_repository.repository_url,
            ),
			opts=ResourceOptions(parent=self, depends_on=[backend_api_ecr_repository]),
        )

        # Spin up a load balanced service running the container image.
        api_ecs_task_definition = aws.ecs.TaskDefinition(f'{name}-task',
            family='fargate-task-definition',
            cpu='256',
            memory='512',
            network_mode='awsvpc',
            requires_compatibilities=['FARGATE'],
            execution_role_arn=args.role.arn,
            container_definitions=Output.all(image_name=backend_api_image.image_name).apply(lambda args: json.dumps(([{
		        'name': 'infra-api',
		        'image': f'{args["image_name"]}',
		        'portMappings': [{
			        'containerPort': 5000,
			        'hostPort': 5000,
			        'protocol': 'tcp'
		        }]
	        }]))),
	        tags=args.tags,
            opts=ResourceOptions(parent=self)
        )

        self.api_service = aws.ecs.Service(f'{name}-svc',
	        cluster=args.cluster.arn,
            desired_count=3,
            launch_type='FARGATE',
            task_definition=api_ecs_task_definition.arn,
            network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
		        assign_public_ip=True,
		        subnets=args.subnet_ids,
		        security_groups=args.security_group_ids,
	        ),
            load_balancers=[aws.ecs.ServiceLoadBalancerArgs(
		        target_group_arn=api_atg.arn,
		        container_name='infra-api',
		        container_port=5000,
	        )],
            opts=ResourceOptions(parent=self, depends_on=[api_lb_listener]),
	        tags=args.tags,
        )

        self.register_outputs({})