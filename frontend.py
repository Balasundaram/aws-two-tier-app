import json

import pulumi_aws as aws
from pulumi import ComponentResource, Output, ResourceOptions
from pulumi_docker import Image, DockerBuildArgs, RegistryArgs
import json

class FrontendServiceArgs:

    def __init__(self,
                 backend_api=None,
                 vpc_id=None,
                 subnet_ids=None,  # array of subnet IDs
                 security_group_ids=None,  # array of security group Ids
                 ecs_cluster=None,
                 role=None,
                 tags=None):
        self.backend_api = backend_api
        self.vpc_id = vpc_id
        self.subnet_ids = subnet_ids
        self.security_group_ids = security_group_ids
        self.cluster = ecs_cluster
        self.role = role
        self.tags = tags

class FrontendService(ComponentResource):

    def __init__(self,
                 name: str,
                 args: FrontendServiceArgs,
                 opts: ResourceOptions = None):

        super().__init__('custom:resource:Frontend', name, {}, opts)

        # Create a load balancer to listen for HTTP traffic on port 80.
        self.web_alb = aws.lb.LoadBalancer(f'{name}-lb',
	        security_groups=args.security_group_ids,
	        subnets=args.subnet_ids,
	        tags=args.tags,
            opts=ResourceOptions(parent=self)
        )

        web_atg = aws.lb.TargetGroup(f'{name}-atg',
	        port=5000,
	        protocol='HTTP',
	        target_type='ip',
	        vpc_id=args.vpc_id,
	        tags=args.tags,
            opts=ResourceOptions(parent=self)
        )

        web_lb_listener = aws.lb.Listener(f'{name}-listener',
	        load_balancer_arn=self.web_alb.arn,
	        port=80,
	        default_actions=[aws.lb.ListenerDefaultActionArgs(
		        type='forward',
		        target_group_arn=web_atg.arn,
	        )],
	        tags=args.tags,
            opts=ResourceOptions(parent=self)
        )

        #Create the ECR repositories for web and api images
        web_app_ecr_repository = aws.ecr.Repository(f'{name}-repository', 
            tags=args.tags, 
            image_tag_mutability="MUTABLE",
            opts=ResourceOptions(parent=self)
        )

        web_ecr_auth_token = aws.ecr.get_authorization_token_output(
            registry_id=web_app_ecr_repository.registry_id
        )

        #Building the infra-web app image and pushing to ECR repo
        web_app_image = Image(f'{name}-image',
            build=DockerBuildArgs(
                context="infra-web",
                dockerfile="infra-web/Dockerfile",
            ),
            image_name=web_app_ecr_repository.repository_url,
            registry=RegistryArgs(
                username="AWS",
                password=Output.secret(web_ecr_auth_token.password),
                server=web_app_ecr_repository.repository_url,
            ),
			opts=ResourceOptions(parent=self, depends_on=[web_app_ecr_repository]),
        )


        # Creating a Cloudwatch instance to store the logs that the ECS services produce
        infra_web_log_group = aws.cloudwatch.LogGroup(f'{name}-log-group',
            retention_in_days=1,
            name="infra-web-log-group",
	        tags=args.tags,
        )

        web_ecs_task_definition = aws.ecs.TaskDefinition(f'{name}-task',
            family='fargate-task-definition',
            cpu='256',
            memory='512',
            network_mode='awsvpc',
            requires_compatibilities=['FARGATE'],
            execution_role_arn=args.role.arn,
            container_definitions=Output.all(image_name=web_app_image.image_name, api_dns_name=args.backend_api.api_alb.dns_name).apply(lambda args: json.dumps(([{
		        'name': 'infra-web',
		        'image': f'{args["image_name"]}',
		        'portMappings': [{
			    'containerPort': 5000,
			    'hostPort': 5000,
			    'protocol': 'tcp'
		        }],
		        'environment': [
			    {
				    "name": "ApiAddress", "value": f'http://{args["api_dns_name"]}/WeatherForecast',
			    }
		        ],
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-group": f'{name}-log-group',
                        "awslogs-region": aws.config.region,
                        "awslogs-stream-prefix": f'{name}',
                    },
                },
	        }]))),
	        tags=args.tags,
            opts=ResourceOptions(parent=self),
        )

        web_service = aws.ecs.Service(f'{name}-svc',
	        cluster=args.cluster.arn,
            desired_count=3,
            launch_type='FARGATE',
            task_definition=web_ecs_task_definition.arn,
            network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
		        assign_public_ip=True,
		        subnets=args.subnet_ids,
		        security_groups=args.security_group_ids,
	        ),
            load_balancers=[aws.ecs.ServiceLoadBalancerArgs(
		        target_group_arn=web_atg.arn,
		        container_name='infra-web',
		        container_port=5000,
	        )],
            opts=ResourceOptions(depends_on=[web_lb_listener, args.backend_api.api_service]),
	        tags=args.tags,
        )

        self.register_outputs({})