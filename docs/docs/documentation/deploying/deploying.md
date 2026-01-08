---
title: Deploying Agent Mesh
sidebar_position: 500
---

# Deploying Agent Mesh

Moving your Agent Mesh from development to production requires careful consideration of deployment strategies, monitoring capabilities, and troubleshooting approaches. Understanding your options and having robust observability tools ensures your agent mesh operates reliably at scale.

## Selecting Your Deployment Strategy

Production deployments require different considerations than development environments, particularly around scalability, reliability, and security. You can choose containerized deployments using Docker for single-node setups, Kubernetes orchestration for scalable architectures, or hybrid approaches that separate components for independent scaling. Each strategy offers distinct advantages depending on your operational requirements. For comprehensive guidance on evaluating and implementing these approaches, see [Choosing Deployment Options](deployment-options.md).

## Observing Your Agent Mesh

Effective monitoring provides the visibility you need to understand system behavior and maintain optimal operation. The platform offers multiple observability layers that create a complete picture of your system's health. You can visualize request workflows through interactive diagrams, monitor real-time agent status, track message flows at the event broker level, and analyze detailed stimulus logs for forensic analysis. For detailed information on implementing these monitoring tools, see [Monitoring Your Agent Mesh](observability.md).

## Troubleshooting and Debugging Issues

When issues arise in distributed systems, systematic debugging approaches help you quickly identify root causes. The debugging process leverages observability tools in focused ways to isolate problems and understand their causes. You can isolate specific components to reduce complexity, examine stimulus traces for detailed analysis, monitor real-time event broker activity, use interactive debugging tools for code investigation, and invoke agents directly for controlled testing. For step-by-step guidance on applying these strategies, see [Diagnosing and Resolving Problems](debugging.md).

## Production Readiness Considerations

Successful production deployments require attention to security, performance, and operational practices beyond basic functionality. Consider implementing robust secret management, establishing TLS encryption for all communication channels, configuring appropriate resource limits and scaling policies, setting up automated backup procedures, and creating runbooks for common scenarios. For environments with restricted network access, you may need to configure proxy settings to enable communication with external services - see [Proxy Configuration](proxy_configuration.md) for details. These practices ensure your agent mesh operates reliably and securely while providing the foundation for ongoing maintenance and optimization.
