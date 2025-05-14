---
title: CLI Chat
sidebar_position: 50
---

# CLI Chat

You can configure the command-line chat interface (CLI Chat) and integrate it with Solace Agent Mesh. The CLI Chat allows you to communicate with Solace Agent Mesh through your terminal.

:::info[Learn about agents]
Before you configure CLI Chat, we recommend that learn about the Solace Agent Mesh CLI. For more information, see [Solace Agent Mesh CLI](../concepts/cli.md).
:::

## Setting Up the Environment

First, you need to [install Solace Agent Agent and Solace Agent Mesh CLI](../getting-started/installation.md). Then, you'll need to [create a new Solace Agent Mesh (SAM) project](../getting-started/quick-start.md).

## Set Up the REST Interface

The CLI chat uses the REST interface to communicate with Solace Agent Mesh. Depending on your REST interface settings, the CLI Chat may need to authenticate using the REST interface authentication endpoint.

You can configure the CLI Chat when you create the SAM project. You'll need to set the host, port, and endpoint of the REST interface, which together form a URL. During installation, you can enable authentication by adding the required authentication configuration to the `.env` file. The authentication is disabled by default. If authentication is enabled, you'll need to log in to Solace Agent Mesh; otherwise, login is not required.

## Running the CLI Chat

If authentication is enabled in the REST interface, you must log in using the following command before starting a chat:

```sh
sam chat login SERVER
```

Where:
- `SERVER`: Use your authentication host address. 

This command provides a URL for OAuth 2.0 authentication. Use the URL to authenticate in your browser to generate a token in JSON format.
- Copy the JSON object that's returned.
- Press Enter in the terminal to paste and save the token.

After successfully logging in, start a chat with the following command:

```sh
sam chat start -a
```

Where:

- `-a`: Specifies an argument that ensures each chat session is authenticated in the background. This argument is not required if authentication is not configured.
During your first chat session after login, the command makes a request for endppoint of the REST interface. Subsequent chats reuse the saved endpoint information until you log out.

**(option)** You can specify the server API endpoint by `-u ENDPOINT` argument. The default API endpoint for a self-hosted SAM is `http://127.0.0.1:5050/api/v1/request`.
```sh
sam chat start -u ENDPOINT
```

The token is automatically renewed using the refresh token in the background, so you only need to log in once. If you no longer need the token, you can log out using:

```sh
sam chat logout
```

This command permanently deletes the token. After logging out, you'll need to log in again to start a new chat.

**(option)** You can upload a file to SAM and add it to the context by `-f FILE_PATH` argument.
```sh
sam chat start -u ENDPOINT -f FILE_PATH
```

