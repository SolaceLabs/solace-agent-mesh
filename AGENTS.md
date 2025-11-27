When I ask questions about agent, gateway and document generation you should follow the below guidline:
1- First use knowledge in llm_vibecoding.txt file and the Context7 MCP tools (via the configured `context7` server) to create the agent or gateway. Do this by default, without requiring me to say “use context7”.
2- If you need more information, use the workspace source code and other tools.
3- Ask user if it prefers to interactively build and run the agent.
4- If the user preferred to build and run the agent interactively, follow steps within <interactive mode> and </interactive mode>. Otherwise, follow steps within <autonomous mode> and </autonomous mode>.

<interactive mode>
4.a.1: Use CLI commands to build and test the agent. Each time ask the user to confirm the command before execution.
4.a.2: Create a python environment and install dependencies if you need to run the CLI.
4.a.3: Ask user to provide the required environment variables if you need.
4.a.4: Verify that all placeholder variables in the configuration files are replaced with appropriate values such as the agent name and display name.
4.a.5: If the test and execution failed, collect logs and update the agent.
4.a.6: Repeat step 4.a.x from the beginning until the agent is run and verified.
</interactive mode>

<autonomous mode>
4.b.1: Implement the agent codes with all required configurations at once without CLI commands.
4.b.2: Verify that all placeholder variables in the configuration files are replaced with appropriate values such as the agent name and display name.
4.b.3: Implement some tests to verify the agent.
4.a.4: If the test failed, collect logs and update the agent.
4.a.5: Repeat step 4.b.X from the beginning until the agent is run and verified.
</autonomous mode>

5- Finally, document the installation, configuration and execution in a README.md file and propose a command to run the agent.
