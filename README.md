# aws-two-tier-app

Steps to deploy the application and its infrastructure, follow these steps:

1. Create a new stack, which is an isolated deployment target for this example:

    ```bash
    $ pulumi stack init prod
    ```

1. Set your desired AWS region:

    ```bash
    $ pulumi config set aws:region us-east-1 # any valid AWS region will work
    ```
1. Configure AWS Credentials

1. Deploy the resources

    ```bash
    $ pulumi up

## Architecture Diagram

![airtek_aws drawio](https://user-images.githubusercontent.com/1333271/235407125-1f57f56b-230c-4663-b273-cda30f9c28ad.png)
