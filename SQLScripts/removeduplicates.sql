delete   from apk_permissions
where    rowid not in
         (
         select  min(rowid)
         from    apk_permissions
         group by
                 apk
         ,       permission
         )