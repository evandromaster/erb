from functools import wraps
from flask import abort, flash, g, jsonify, redirect, request, url_for
from control_database import get_control_connection

ROLE_LEVEL={'view':1,'editor':2,'admin':3}

def login_required(view):
    @wraps(view)
    def wrapped(*args,**kwargs):
        if not getattr(g,'current_user',None):
            if request.path.startswith('/api/') or request.is_json:
                return jsonify(success=False,error='Autenticação necessária.'),401
            flash('Faça login para acessar o ERB Maps.','warning')
            return redirect(url_for('auth.login',next=request.full_path if request.query_string else request.path))
        return view(*args,**kwargs)
    return wrapped

def role_required(role):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args,**kwargs):
            if ROLE_LEVEL.get(g.current_user['type_user'],0)<ROLE_LEVEL[role]: abort(403)
            return view(*args,**kwargs)
        return wrapped
    return decorator

admin_required=role_required('admin')
editor_required=role_required('editor')

def user_has_project_access(user_id,project_id,minimum='view'):
    if not user_id or not project_id:return False
    conn=get_control_connection()
    try:
        user=conn.execute('SELECT type_user,activated FROM users WHERE id=?',(user_id,)).fetchone()
        if not user or not user['activated']:return False
        active=conn.execute('SELECT 1 FROM projects WHERE id=? AND activated=1',(project_id,)).fetchone()
        if not active:return False
        if user['type_user']=='admin':return True
        link=conn.execute('SELECT permission FROM user_projects WHERE user_id=? AND project_id=?',
                          (user_id,project_id)).fetchone()
        if not link:return False
        return min(ROLE_LEVEL[user['type_user']],ROLE_LEVEL[link['permission']])>=ROLE_LEVEL[minimum]
    finally:conn.close()

def project_access_required(minimum='view'):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args,**kwargs):
            pid=g.active_project['id'] if getattr(g,'active_project',None) else None
            if not user_has_project_access(g.current_user['id'],pid,minimum):abort(403)
            return view(*args,**kwargs)
        return wrapped
    return decorator
