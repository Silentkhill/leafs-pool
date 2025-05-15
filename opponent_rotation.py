# This file contains the opponent rotation logic with playoff mode support

def check_opponent_change_and_rotate():
    """Check if the opponent has changed and rotate the draft order if needed"""
    try:
        # File to store the last opponent
        import os
        import json
        
        # Check if playoff mode is enabled
        from app import Settings, logger, app, rotate_draft_order, get_current_opponent
        from app import get_next_game, get_next_picker, send_notification
        
        playoff_mode = Settings.get('playoff_mode', 'false').lower() == 'true'
        
        if playoff_mode:
            # In playoff mode, we check for game date change instead of opponent change
            next_game_info = get_next_game()
            if not next_game_info:
                logger.warning("Could not get next game information")
                return False
                
            next_game_date = next_game_info.get('game_time').date().isoformat() if next_game_info.get('game_time') else None
            last_game_date_file = os.path.join(app.root_path, 'last_game_date.json')
            
            # If file doesn't exist, create it with current game date
            if not os.path.exists(last_game_date_file):
                with open(last_game_date_file, 'w') as f:
                    json.dump({"last_game_date": next_game_date}, f)
                logger.info(f"Created last game date file with {next_game_date}")
                return False
            
            # Read the last game date
            with open(last_game_date_file, 'r') as f:
                data = json.load(f)
                last_game_date = data.get("last_game_date")
            
            # Check if game date has changed
            if last_game_date != next_game_date:
                logger.info(f"Game date changed from {last_game_date} to {next_game_date}")
                
                # Update the file with new game date
                with open(last_game_date_file, 'w') as f:
                    json.dump({"last_game_date": next_game_date}, f)
                
                # Rotate the draft order
                rotated = rotate_draft_order()
                if rotated:
                    logger.info("Draft order rotated due to game date change (playoff mode)")
                    
                    # Get next picker and notify them
                    if next_game_info.get('game_time'):
                        next_picker = get_next_picker(next_game_info.get('game_time'))
                        if next_picker:
                            logger.info(f"Notifying next picker after rotation: {next_picker.username}")
                            send_notification(next_picker, next_game_info.get('game_time'))
                    
                    return True
            
            return False
        else:
            # Regular season mode - check opponent change
            last_opponent_file = os.path.join(app.root_path, 'last_opponent.json')
            current_opponent = get_current_opponent()
            
            if not current_opponent:
                logger.warning("Could not get current opponent information")
                return False
            
            # If file doesn't exist, create it with current opponent
            if not os.path.exists(last_opponent_file):
                with open(last_opponent_file, 'w') as f:
                    json.dump({"last_opponent": current_opponent}, f)
                logger.info(f"Created last opponent file with {current_opponent}")
                return False
            
            # Read the last opponent
            with open(last_opponent_file, 'r') as f:
                data = json.load(f)
                last_opponent = data.get("last_opponent")
            
            # Check if opponent has changed
            if last_opponent != current_opponent:
                logger.info(f"Opponent changed from {last_opponent} to {current_opponent}")
                
                # Update the file with new opponent
                with open(last_opponent_file, 'w') as f:
                    json.dump({"last_opponent": current_opponent}, f)
                
                # Rotate the draft order
                rotated = rotate_draft_order()
                if rotated:
                    logger.info("Draft order rotated due to opponent change")
                    
                    # Get next picker and notify them
                    next_game_info = get_next_game()
                    if next_game_info and next_game_info.get('game_time'):
                        next_game_time = next_game_info.get('game_time')
                        next_picker = get_next_picker(next_game_time)
                        if next_picker:
                            logger.info(f"Notifying next picker after rotation: {next_picker.username}")
                            send_notification(next_picker, next_game_time)
                    
                    return True
            
            return False
    except Exception as e:
        logger.error(f"Error checking opponent change: {str(e)}")
        return False