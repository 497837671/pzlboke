from flask import render_template, session, redirect, url_for, current_app,\
    abort, flash, request, current_app, make_response
from .. import db
from ..models import User, Role, Post, Permission, Comment
from ..email import send_email
from . import main
from .forms import NameForm
from datetime import datetime
from flask_login import login_required, current_user
from ..decorators import admin_required, permission_required
from .forms import EditProfileForm, EditProfileAdminForm, PostForm, CommentForm
from sqlalchemy import or_


@main.route('/pzl', methods=['GET', 'POST'])
@login_required
def pzl():
    form = NameForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.name.data).first()
        if user is None:
            user = User(username=form.name.data)
            db.session.add(user)
            db.session.commit()
            session['known'] = False
            if current_app.config['FLASKY_ADMIN']:
                send_email(current_app.config['FLASKY_ADMIN'], 'New User',
                           'mail/new_user', user=user)
        else:
            session['known'] = True
        session['name'] = form.name.data
        return redirect(url_for('.pzl'))
    return render_template('pzl.html',
                           form=form, name=session.get('name'),
                           known=session.get('known', False),
                           current_time=datetime.utcnow())


@main.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('user.html', user=user, posts=posts,
                           pagination=pagination, current_time=datetime.utcnow())


@main.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user._get_current_object())
        db.session.commit()
        flash('您的资料已更新。')
        return redirect(url_for('.user', username=current_user.username))
    form.name.data = current_user.name
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', form=form,
                           current_time=datetime.utcnow())


@main.route('/edit-profile/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_profile_admin(id):
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.confirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.name = form.name.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        db.session.add(user)
        db.session.commit()
        flash('您的资料已更新。')
        return redirect(url_for('.user', username=user.username))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.name.data = user.name
    form.location.data = user.location
    form.about_me.data = user.about_me
    return render_template('edit_profile.html', form=form, user=user,
                           current_time=datetime.utcnow())


@main.route('/', methods=['GET', 'POST'])
def index():
    form = PostForm()
    # 判断是否属于有权限用户，有权限才可以使用提交评论
    if (current_user.can(Permission.WRITE) or current_user.can(Permission.ADMIN)) and form.validate_on_submit():
        post = Post(title=form.title.data,
                    body=form.body.data,
                    author=current_user._get_current_object())
        db.session.add(post)
        db.session.commit()
        return redirect(url_for('.index'))
    # 分页显示博客文章列表
    # 渲染的页数从请求的查询字符串（request.args）中获取，如果没有明确指定，则默认渲染第 1 页。
    # 参数 type=int 确保参数在无法转换成整数时返回默认值。
    page = request.args.get('page', 1, type=int)

    # 显示所有博客文章或只显示所关注用户的文章
    show_followed = False
    if current_user.is_authenticated:
        show_followed = bool(request.cookies.get('show_followed', ''))
    if show_followed:
        query = current_user.followed_posts
    else:
        query = Post.query

    # Post.timestamp.desc()时间戳排序
    # paginate() 方法的第一个参数——也是唯一必需的参数——是
    # 页数。可选参数 per_page 指定每页显示的记录数量；如果没有指定，则默认显示 20 个记录。
    pagination = query.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('index.html', form=form, posts=posts,
                           show_followed=show_followed, pagination=pagination,
                           current_time=datetime.utcnow())


# 为文章提供固定链接
# 支持博客文章评论
@main.route('/post/<int:id>', methods=['GET', 'POST'])
def post(id):
    post = Post.query.get_or_404(id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(body=form.body.data,
                          post=post,
                          author=current_user._get_current_object())
        db.session.add(comment)
        db.session.commit()
        flash('你已提交评论')
        return redirect(url_for('.post', id=post.id, page=-1))
    page = request.args.get('page', 1, type=int)
    if page == -1:
        page = (post.comments.count() - 1) // \
            current_app.config['FLASKY_COMMENTS_PER_PAGE'] + 1
    pagination = post.comments.order_by(Comment.timestamp.asc()).paginate(
        page, per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('post.html', posts=[post], form=form,
                           comments=comments, pagination=pagination,
                           current_time=datetime.utcnow())


# 回复评论视图
@main.route('/postee/<int:id>', methods=['GET', 'POST'])
def postee(id):
    post = Comment.query.get_or_404(id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(body=form.body.data,
                          post=post,
                          author=current_user._get_current_object())
        db.session.add(comment)
        db.session.commit()
        flash('你已提交评论')
        return redirect(url_for('.post', id=post.id, page=-1))


# 删除评论路由
@main.route('/delete_comment/<int:id>')
def delete_comment(id):
    comment = Comment.query.get_or_404(id)
    if current_user != comment.author and \
            not current_user.can(Permission.ADMIN):
        abort(403)
    #Post.query.filter(post.id).delete()
    db.session.delete(comment)
    db.session.commit()
    flash("删除成功")
    return render_template('delete_comment.html', current_time=datetime.utcnow())


# 编辑博客文章的路由
@main.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    post = Post.query.get_or_404(id)
    # 判断是否本用户，或者管理员。如果不是则返回403
    if current_user != post.author and \
            not current_user.can(Permission.ADMIN):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.body = form.body.data
        db.session.add(post)
        db.session.commit()
        flash('这篇文章已成功更新.')
        return redirect(url_for('.post', id=post.id))
    # 编辑时，显示之前的默认值
    form.title.data = post.title
    form.body.data = post.body
    return render_template('edit_post.html', form=form,
                           current_time=datetime.utcnow())


# 删除博客文章的路由
@main.route('/delete_post/<int:id>')
def delete_post(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and \
            not current_user.can(Permission.ADMIN):
        abort(403)
    #Post.query.filter(post.id).delete()
    db.session.delete(post)
    db.session.commit()
    flash("删除成功")
    return render_template('delete_post.html', current_time=datetime.utcnow())


@main.route('/follow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('没找到该用户')
        return redirect(url_for('.index'))
    if current_user.is_following(user):
        flash('你已经关注了这个用户')
        return redirect(url_for('.user', username=username))
    current_user.follow(user)
    db.session.commit()
    flash('成功关注 %s.' % username)
    return redirect(url_for('.user', username=username))


@main.route('/unfollow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('没找到该用户')
        return redirect(url_for('.index'))
    if not current_user.is_following(user):
        flash('你没有关注该用户')
        return redirect(url_for('.user', username=username))
    current_user.unfollow(user)
    db.session.commit()
    flash('您已对 %s 取消关注' % username)
    return redirect(url_for('.user', username=username))


@main.route('/followers/<username>')
def followers(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('没找到该用户')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followers.paginate(
        page, per_page=current_app.config['FLASKY_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.follower, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title="的粉丝列表",
                           endpoint='.followers', pagination=pagination,
                           follows=follows, current_time=datetime.utcnow())


@main.route('/followed_by/<username>')
def followed_by(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('没找到该用户')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followed.paginate(
        page, per_page=current_app.config['FLASKY_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.followed, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title="的关注列表",
                           endpoint='.followed_by', pagination=pagination,
                           follows=follows, current_time=datetime.utcnow())


@main.route('/all')
@login_required
def show_all():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '', max_age=30*24*60*60)
    return resp


@main.route('/followed')
@login_required
def show_followed():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '1', max_age=30*24*60*60)
    return resp


@main.route('/moderate')
@login_required
@permission_required(Permission.MODERATE)
def moderate():
    page = request.args.get('page', 1, type=int)
    pagination = Comment.query.order_by(Comment.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('moderate.html', comments=comments,
                           pagination=pagination, page=page,
                           current_time=datetime.utcnow())


@main.route('/moderate/enable/<int:id>')
@login_required
@permission_required(Permission.MODERATE)
def moderate_enable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = False
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))


@main.route('/moderate/disable/<int:id>')
@login_required
@permission_required(Permission.MODERATE)
def moderate_disable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = True
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))


# 编辑博客文章的路由
@main.route('/abc/<int:id>', methods=['GET', 'POST'])
@login_required
def abc(id):
    flash('回复功能正在开发中')
    return render_template('abc.html',
                           current_time=datetime.utcnow())


# 搜索路由
@main.route('/search')
def search():
    # /search?q=xxx
    q = request.args.get("q")
    # 页码还有bug 待改进
    # page = request.args.get('page', 1, type=int)
    posts = Post.query.filter(or_(Post.body.contains(q), Post.title.contains(q))).order_by(Post.timestamp.desc())
    if current_user.is_authenticated:
        form = PostForm()
        return render_template("index.html", posts=posts, form=form,
                               current_time=datetime.utcnow())
    else:
        return render_template("index.html", posts=posts,
                               current_time=datetime.utcnow())


    # pagination = query.order_by(Post.timestamp.desc()).paginate(
    #     page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
    #     error_out=False)
    # posts = pagination.items
    # return render_template('index.html', form=form, posts=posts,
    #                        show_followed=show_followed, pagination=pagination,
    #                        current_time=datetime.utcnow())


