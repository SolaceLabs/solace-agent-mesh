---
title: LLM Models
sidebar_position: 12
---

# LLM Models

## Configuring Different LLM Models

## SSL/TLS Configuration 

Solace agent mesh allows for fine tunning SSL connection to your LLM endpoints through environment variables. The connection parameters are described in the following table:

| Parameter                  | Type      | Description                                                        | Default   |
|----------------------------|-----------|--------------------------------------------------------------------|-----------|
| `SSL_VERIFY`               | `boolean` | Controls SSL certificate verification for outbound connections.    | `true`    |
| `SSL_SECURITY_LEVEL`       | `integer` | Sets the SSL security level (higher values enforce stricter checks). | `2`       |
| `SSL_CERT_FILE`            | `string`  | Path to a custom SSL certificate file to use for verification.     | (none)    |
| `SSL_CERTIFICATE`          | `string`  | Direct content of the SSL certificate (PEM format).                | (none)    |
| `DISABLE_AIOHTTP_TRANSPORT`| `boolean` | Flag to disable the use of aiohttp transport for HTTP requests.    | `false`   |
| `AIOHTTP_TRUST_ENV`        | `boolean` | Flag to enable aiohttp to trust environment proxy settings.        | `false`   |
