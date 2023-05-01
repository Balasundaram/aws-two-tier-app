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

![airtek_aws drawio (1)](https://user-images.githubusercontent.com/1333271/235488005-3370985b-ff9e-416e-bce6-2c91a1b0ec76.png)
