# jira_insight_backup
Script for backup/restore Jira Insight schemas, object types, attributes. Objects are NOT backuping/restoring yet. 
Default schema keys: BUSASSETS,GEN,ITASSETS,ITDM,JAG,OMS,PEOPLE,SVC,WP

# How to run
```
./insight_backup_tool.py --workspace-id <uuid> --data-dir <absolute or relative path> --username <login username> --password <login password> --action <backup/restore>
