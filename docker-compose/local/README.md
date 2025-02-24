# Development

1. Go to the current directory:

    ```sh
    cd docker-compose/local
    ```

2. Access to the **remote** DIAL Core server is specified by env vars `$REMOTE_DIAL_URL` and `$REMOTE_DIAL_API_KEY`.

    Run the following command to generate **local** DIAL Core config `core/config.json` based on the listing from the **remote** DIAL Core:

    ```sh
    REMOTE_DIAL_URL="url" REMOTE_DIAL_API_KEY="key" ./generate_config_from_listing.sh
    ```

    This script requires installed Python.

    Use a simple config template, if you are experiencing issues running the script above:

    ```sh
    REMOTE_DIAL_URL="url" REMOTE_DIAL_API_KEY="key" ./generate_config_from_template.sh
    ```

3. The script also adds definition of a sample locally hosted application to the DIAL config. This allows to call an application served at `http://localhost:5005/openai/deployments/app/chat/completions` from the local DIAL chat.

4. Modify the generated `core/config.json` as you see fit: add required models and applications hosted by the remote DIAL server, configure locally hosted applications.

5. Finally, run the local DIAL Core and DIAL Chat via:

    ```sh
    docker compose up --abort-on-container-exit
    ```

    when running under root. Otherwise, run:

    ```sh
    UID=$(id -u) docker compose up --abort-on-container-exit
    ```

    > [!NOTE]
    > The docker-compose file uses `latest` tag for the DIAL components. Once the images are pulled from the repository, the Docker won't pull it again and use the cached image. To update the images, run the following before starting the containers:
    > ```sh
    > docker compose pull
    > ```

6. Open local DIAL Chat at [http://localhost:3000](http://localhost:3000)
