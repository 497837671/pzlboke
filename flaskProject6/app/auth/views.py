from flask import render_template, redirect, request, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from . import auth
from ..models import User, Follow
from .forms import LoginForm
from datetime import datetime
from .forms import LoginForm, RegistrationForm, ChangePasswordForm, \
    PasswordResetRequestForm, PasswordResetForm, ChangeEmailForm
from .. import db
from ..email import send_email


@auth.before_app_request
def before_request():
    if current_user.is_authenticated:
        # 更新已登录用户的最后访问时间
        current_user.ping()
        if not current_user.confirmed \
                and request.endpoint \
                and request.blueprint != 'auth' \
                and request.endpoint != 'static':
            return redirect(url_for('auth.unconfirmed'))


@auth.route('/unconfirmed')
def unconfirmed():
    if current_user.is_anonymous or current_user.confirmed:
        return redirect(url_for('main.index'))
    return render_template('auth/unconfirmed.html',
                           current_time=datetime.utcnow())


@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            next = request.args.get('next')
            if next is None or not next.startswith('/'):
                next = url_for('main.index')
            return redirect(next)
        flash('邮箱或密码错误')
    return render_template('auth/login.html', form=form,
                           current_time=datetime.utcnow())


# 注销账号，返回登录页面
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已退出账号')
    return redirect(url_for('auth.login'))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data.lower(),
                    name=form.name.data,
                    location=form.location.data,
                    username=form.username.data,
                    password=form.password.data)
        db.session.add(user)
        db.session.commit()
        token = user.generate_confirmation_token()
        send_email(user.email, '请确认您的账户',
                   'auth/email/confirm', user=user, token=token)
        flash('确认邮件已通过电子邮件发送给您，请查收')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form,
                           current_time=datetime.utcnow())


@auth.route('/confirm/<token>')
@login_required
def confirm(token):
    if current_user.confirmed:
        return redirect(url_for('main.index'))
    if current_user.confirm(token):
        db.session.commit()
        flash('您已确认账户。感谢!')
    else:
        flash('确认链接无效或已过期。')
    return redirect(url_for('main.index'))


@auth.route('/confirm')
@login_required
def resend_confirmation():
    token = current_user.generate_confirmation_token()
    send_email(current_user.email, '请确认您的账户',
               'auth/email/confirm', user=current_user, token=token)
    flash('一封新的确认邮件已经通过电子邮件发给您了。')
    return redirect(url_for('main.index'))


@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.old_password.data):
            current_user.password = form.password.data
            db.session.add(current_user)
            db.session.commit()
            flash('你的密码已修改')
            return redirect(url_for('main.index'))
        else:
            flash('请输入正确的密码')
    return render_template("auth/change_password.html", form=form,
                           current_time=datetime.utcnow())


@auth.route('/reset', methods=['GET', 'POST'])
def password_reset_request():
    if not current_user.is_anonymous:
        return redirect(url_for('main.index'))
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            token = user.generate_reset_token()
            send_email(user.email, '重置密码',
                       'auth/email/reset_password',
                       user=user, token=token)
        flash('一封提示重置密码的电子邮件已经发送给你。 ')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', form=form,
                           current_time=datetime.utcnow())


@auth.route('/reset/<token>', methods=['GET', 'POST'])
def password_reset(token):
    if not current_user.is_anonymous:
        return redirect(url_for('main.index'))
    form = PasswordResetForm()
    if form.validate_on_submit():
        if User.reset_password(token, form.password.data):
            db.session.commit()
            flash('您的密码已更新!')
            return redirect(url_for('auth.login'))
        else:
            return redirect(url_for('main.index'))
    return render_template('auth/reset_password.html', form=form,
                           current_time=datetime.utcnow())


@auth.route('/change_email', methods=['GET', 'POST'])
@login_required
def change_email_request():
    form = ChangeEmailForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.password.data):
            new_email = form.email.data.lower()
            token = current_user.generate_email_change_token(new_email)
            send_email(new_email, '确认您的电子邮件地址',
                       'auth/email/change_email',
                       user=current_user, token=token)
            flash('一封带有说明的电子邮件，以确认您的新电子邮件地址已发送给您。 ')
            return redirect(url_for('main.index'))
        else:
            flash('邮箱地址或密码错误')
    return render_template("auth/change_email.html", form=form,
                           current_time=datetime.utcnow())


@auth.route('/change_email/<token>')
@login_required
def change_email(token):
    if current_user.change_email(token):
        db.session.commit()
        flash('您的电子邮件地址已更新。')
    else:
        flash('Invalid request.')
    return redirect(url_for('main.index'))
