select permission, (select info from permissions where id = permission ), count(permission) from apk_permissions group by permission ORDER BY count(permission) DESC

select id, info, count(permission) from apk_permissions INNER JOIN permissions ON apk_permissions.permission = permissions.id group by permission ORDER BY count(permission) DESC