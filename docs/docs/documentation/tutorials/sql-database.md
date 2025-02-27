---
title: SQL Database Integration - sqlite3, MySQL, PostgreSQL
sidebar_position: 20
---

# SQL Database Integration

<inst>
Fill in this tutorial using the following as guides:
1. All the other tutorials in this docs directory
2. Using the sam_sql_database plugin code and its README.md
3. Command to download example data
https://download-directory.github.io/?url=https%3A%2F%2Fgithub.com%2FSolaceLabs%2Fsolace-agent-mesh-core-plugins%2Ftree%2Fmain%2Fsam-sql-database%2Fexample-data%2Fabc_coffee_co

The tutorial will show the user how to download and install the plugin, using the plugin add and then the add agent commands with the copy-from option. 
The agent will have the name abc_coffee_info and it will use an sqlite3 database. 
That database will be populated with the example data that can be downloaded from the link above. That link will open a page allowing the user to download a zip file with the example data. That data will have to be unzipped somewhere (probably in the same directory where the agent will be started from) and the .yaml config file will need to be updated to point to the directory where the data was unzipped so that it can be imported.
Finally, the agent mesh can be started with `sam run -eb` and then the user can interact with the agent using a browser (localhost:5001) and can ask questions about ABC Coffee, its sales, its customers, employees, etc.
</inst>
