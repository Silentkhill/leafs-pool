# Admin routes for the Leafs Pool application

from flask import flash, redirect, url_for
from flask_login import login_required, current_user
import logging

logger = logging.getLogger('admin_routes')

def admin_route(app, Settings):
    """Define admin routes for the application"""
    
    @app.route('/admin/toggle-playoff-mode', methods=['POST'])
    @login_required
    def toggle_playoff_mode():
        """Toggle playoff mode on/off"""
        if not current_user.is_admin:
            flash('Access denied: Admin privileges required', 'danger')
            return redirect(url_for('home'))
        
        try:
            # Get current playoff mode status
            current_mode = Settings.get('playoff_mode', 'false').lower() == 'true'
            
            # Toggle it
            new_mode = not current_mode
            Settings.set('playoff_mode', str(new_mode).lower())
            
            # Show success message
            if new_mode:
                flash('Playoff mode enabled! Rotation will now occur by game date instead of opponent change.', 'success')
            else:
                flash('Playoff mode disabled! Rotation will now occur by opponent change.', 'info')
        except Exception as e:
            logger.error(f"Error toggling playoff mode: {str(e)}")
            flash(f'Error toggling playoff mode: {str(e)}', 'danger')
        
        return redirect(url_for('admin'))
    
    @app.route('/admin')
    @login_required
    def admin():
        """Admin dashboard view"""
        if not current_user.is_admin:
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('home'))
        
        from app import User
        users = User.query.all()
        
        # Get settings for the template
        settings = {}
        for setting in Settings.query.all():
            settings[setting.key] = setting.value
        
        return render_template('admin.html', users=users, settings=settings)
    
    return app