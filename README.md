# Leafs Pool Application

A web application for managing a Toronto Maple Leafs hockey pool.

## New Feature: Playoff Mode

### Problem Solved
During the regular season, the app rotates the draft order when the opponent team changes. However, during playoff series, the Leafs play against the same team for multiple consecutive games. This means the opponent-based rotation doesn't trigger since the opponent team doesn't change.

### Solution
The new Playoff Mode feature changes how the draft order rotation works:

- **Regular Season Mode (default)**: Rotates the draft order when the opponent team changes
- **Playoff Mode**: Rotates the draft order when the game date changes, regardless of opponent

### How to Use

1. Log in as an admin
2. Go to the Admin Panel
3. In the "Draft Order Management" section, click the "Enable Playoff Mode" button
4. When playoff series are over, click "Disable Playoff Mode" to return to regular season behavior

### Technical Details

- Added a `Settings` database model to store application-wide configuration
- Modified the opponent change checker to respect the playoff mode setting
- Added a toggle button to the admin interface
- Updated the UI to clearly show which mode is currently active

### Files Modified

- `app.py`: Added Settings model and core functionality
- `opponent_rotation.py`: Added playoff mode logic to the rotation function
- `admin_routes.py`: Added admin route for toggling playoff mode
- `templates/admin.html`: Updated admin template with playoff mode toggle button and status indicator