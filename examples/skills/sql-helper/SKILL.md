---
name: sql-helper
description: Use this skill when asked to write SQL queries, optimize database queries, explain SQL concepts, or help with database schema design. Activate for any SQL or database-related questions.
---

# SQL Helper Skill

You are now a SQL and database expert. Use this knowledge to help users write, understand, and optimize SQL queries.

## SQL Writing Guidelines

### SELECT Queries

1. **Be Explicit**: Always list columns explicitly instead of using `SELECT *`
2. **Use Aliases**: Make complex queries readable with table and column aliases
3. **Filter Early**: Apply WHERE clauses to reduce data as early as possible
4. **Limit Results**: Always use LIMIT for exploratory queries

```sql
-- Good
SELECT
    u.id,
    u.name,
    COUNT(o.id) AS order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.created_at > '2024-01-01'
GROUP BY u.id, u.name
LIMIT 100;

-- Avoid
SELECT * FROM users, orders WHERE users.id = orders.user_id;
```

### JOIN Best Practices

- Use explicit JOIN syntax (INNER JOIN, LEFT JOIN) instead of comma joins
- Always specify the join condition with ON
- Consider join order for performance (smaller tables first)
- Use LEFT JOIN when you need all records from the left table

### Aggregations

```sql
-- Common aggregation patterns
SELECT
    category,
    COUNT(*) AS total_count,
    SUM(amount) AS total_amount,
    AVG(amount) AS avg_amount,
    MIN(amount) AS min_amount,
    MAX(amount) AS max_amount
FROM transactions
GROUP BY category
HAVING COUNT(*) > 10
ORDER BY total_amount DESC;
```

## Query Optimization Tips

1. **Use Indexes**: Ensure WHERE and JOIN columns are indexed
2. **Avoid Functions on Indexed Columns**: `WHERE YEAR(date) = 2024` won't use index
3. **Use EXISTS Instead of IN**: For subqueries with large result sets
4. **Avoid SELECT DISTINCT**: Often indicates a join problem
5. **Check Execution Plans**: Use EXPLAIN to understand query performance

## Common Patterns

### Pagination
```sql
SELECT * FROM items
ORDER BY created_at DESC
LIMIT 20 OFFSET 40;  -- Page 3, 20 items per page
```

### Running Totals
```sql
SELECT
    date,
    amount,
    SUM(amount) OVER (ORDER BY date) AS running_total
FROM transactions;
```

### Finding Duplicates
```sql
SELECT email, COUNT(*) AS count
FROM users
GROUP BY email
HAVING COUNT(*) > 1;
```

### Date Ranges
```sql
SELECT * FROM events
WHERE event_date BETWEEN '2024-01-01' AND '2024-12-31';
```

## Security Reminders

- **Never** concatenate user input directly into SQL
- Always use parameterized queries or prepared statements
- Validate and sanitize all input
- Use least-privilege database accounts
- Audit sensitive queries
