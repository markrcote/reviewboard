from django.contrib.auth.models import User

def get_or_create_bugzilla_users(user_data):
    users_db = []
    for user in user_data['users']:
        username = user['email']
        real_name = user['real_name']
        can_login = user['can_login']
        modified = False
        try:
            user_db = User.objects.get(username=username)
        except User.DoesNotExist:
            user_db = User(username=username, password='from bugzilla',
                           first_name=real_name, email=username,
                           is_active=can_login)
            modified = True
        else:
            if user_db.first_name != real_name:
                user_db.first_name = real_name
                modified = True
            if user_db.is_active != can_login:
                user_db.is_active = can_login
                modified = True
        if modified:
            user_db.save()
        users_db.append(user_db)
    return users_db

