$repo = "C:\Users\Administrator\Desktop\Github\Senhuang_linebot2\Senhuang_linebot"
git -C $repo add .
git -C $repo commit -m "Fix 405 Method Not Allowed error for periodic payments"
git -C $repo push
