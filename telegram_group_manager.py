# Add sort dropdown
        sort_label = QLabel("Sort by:")
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Name (A-Z)", "Name (Z-A)", "ID (Low-High)", "ID (High-Low)"])
        self.sort_combo.currentIndexChanged.connect(self.sort_groups)
        search_sort_layout.addWidget(sort_label)
        search_sort_layout.addWidget(self.sort_combo)#!/usr/bin/env python3
"""
Telegram Group & Channel Manager with GUI

This script provides a graphical interface to help you manage your Telegram groups and channels.
It allows you to select which groups and channels to keep and leave all others.
"""

import sys
import os
import csv
import asyncio
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QCheckBox, 
                            QScrollArea, QMessageBox, QProgressBar, QGroupBox,
                            QGridLayout, QFrame, QFileDialog, QTextEdit,
                            QLineEdit, QComboBox, QListWidget, QListWidgetItem)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon, QColor, QPalette

from telethon import TelegramClient
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.messages import DeleteChatUserRequest
from telethon.tl.types import PeerChannel, PeerChat

# Configuration variables
SESSION_NAME = "telegram_group_manager_session"
GROUPS_TO_KEEP_FILE = "groups_to_keep.txt"
CONFIG_FILE = "telegram_config.txt"

class TelegramWorker(QThread):
    """Worker thread for Telegram operations to avoid freezing the GUI"""
    update_status = pyqtSignal(str)
    update_progress = pyqtSignal(int)
    fetched_groups = pyqtSignal(list)
    operation_complete = pyqtSignal(bool, str)
    
    def __init__(self, api_id, api_hash, phone_number, action, groups_to_leave=None):
        super().__init__()
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.action = action  # 'fetch_groups' or 'leave_groups'
        self.groups_to_leave = groups_to_leave
        
    async def create_client(self):
        """Create and connect the Telegram client"""
        self.update_status.emit("Connecting to Telegram...")
        
        client = TelegramClient(SESSION_NAME, self.api_id, self.api_hash)
        await client.start(phone=self.phone_number)
        
        if not await client.is_user_authorized():
            self.update_status.emit("Authentication failed. Please check your credentials.")
            self.operation_complete.emit(False, "Authentication failed")
            return None
            
        self.update_status.emit("Connected to Telegram successfully")
        return client
        
    async def fetch_groups(self):
        """Fetch all groups from Telegram"""
        client = await self.create_client()
        if not client:
            return
            
        self.update_status.emit("Fetching your groups...")
        
        try:
            dialogs = await client.get_dialogs()
            
            groups = []
            for dialog in dialogs:
                entity = dialog.entity
                if hasattr(entity, 'megagroup') and entity.megagroup:
                    groups.append({
                        'id': entity.id,
                        'name': dialog.name,
                        'type': 'supergroup'
                    })
                elif hasattr(entity, 'chat_id'):
                    groups.append({
                        'id': entity.id,
                        'name': dialog.name, 
                        'type': 'group'
                    })
                elif hasattr(entity, 'broadcast') and entity.broadcast:
                    groups.append({
                        'id': entity.id,
                        'name': dialog.name,
                        'type': 'channel'
                    })
                    
            self.update_status.emit(f"Found {len(groups)} groups")
            self.fetched_groups.emit(groups)
            self.operation_complete.emit(True, f"Found {len(groups)} groups")
            
        except Exception as e:
            self.update_status.emit(f"Error fetching groups: {str(e)}")
            self.operation_complete.emit(False, f"Error: {str(e)}")
        finally:
            await client.disconnect()
    
    async def leave_groups(self):
        """Leave the specified groups"""
        client = await self.create_client()
        if not client:
            return
            
        total_groups = len(self.groups_to_leave)
        self.update_status.emit(f"Leaving {total_groups} groups...")
        
        # Setup log file
        log_file = f"leave_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(log_file, 'w', newline='', encoding='utf-8') as log:
            writer = csv.writer(log)
            writer.writerow(["Group ID", "Group Name", "Status", "Message", "Timestamp"])
            
            for i, group in enumerate(self.groups_to_leave):
                group_id = group['id']
                group_name = group['name']
                
                progress = int((i / total_groups) * 100)
                self.update_progress.emit(progress)
                self.update_status.emit(f"Leaving group: {group_name}")
                
                try:
                    if group['type'] == 'supergroup' or group['type'] == 'channel':
                        entity = await client.get_entity(PeerChannel(int(group_id)))
                        await client(LeaveChannelRequest(entity))
                        status = "Success"
                        message = "Left successfully"
                    else:
                        entity = await client.get_entity(PeerChat(int(group_id)))
                        await client(DeleteChatUserRequest(
                            chat_id=entity.id,
                            user_id='me'
                        ))
                        status = "Success"
                        message = "Left successfully"
                except Exception as e:
                    status = "Failed"
                    message = str(e)
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow([group_id, group_name, status, message, timestamp])
                
                # Avoid flooding
                await asyncio.sleep(1)
        
        self.update_progress.emit(100)
        self.update_status.emit(f"Operation complete. Results saved to {log_file}")
        self.operation_complete.emit(True, f"Operation complete. Results saved to {log_file}")
        
        await client.disconnect()
        
    def run(self):
        """Run the worker thread"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if self.action == 'fetch_groups':
                loop.run_until_complete(self.fetch_groups())
            elif self.action == 'leave_groups':
                loop.run_until_complete(self.leave_groups())
        finally:
            loop.close()

class TelegramGroupManager(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.groups = []
        self.original_groups = []
        self.load_config()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Telegram Group & Channel Manager")
        self.setMinimumSize(700, 600)
        
        # Create central widget and main layout
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        
        # Create API credentials section
        creds_group = QGroupBox("Telegram API Credentials")
        creds_layout = QGridLayout()
        
        self.api_id_label = QLabel("API ID:")
        self.api_id_input = QTextEdit()
        self.api_id_input.setFixedHeight(30)
        
        self.api_hash_label = QLabel("API Hash:")
        self.api_hash_input = QTextEdit()
        self.api_hash_input.setFixedHeight(30)
        
        self.phone_label = QLabel("Phone Number:")
        self.phone_input = QTextEdit()
        self.phone_input.setFixedHeight(30)
        self.phone_input.setPlaceholderText("+12345678901")
        
        creds_layout.addWidget(self.api_id_label, 0, 0)
        creds_layout.addWidget(self.api_id_input, 0, 1)
        creds_layout.addWidget(self.api_hash_label, 1, 0)
        creds_layout.addWidget(self.api_hash_input, 1, 1)
        creds_layout.addWidget(self.phone_label, 2, 0)
        creds_layout.addWidget(self.phone_input, 2, 1)
        
        creds_group.setLayout(creds_layout)
        main_layout.addWidget(creds_group)
        
        # Create button layout
        button_layout = QHBoxLayout()
        
        self.connect_btn = QPushButton("Connect & Fetch Groups/Channels")
        self.connect_btn.clicked.connect(self.fetch_groups)
        
        self.save_config_btn = QPushButton("Save Credentials")
        self.save_config_btn.clicked.connect(self.save_config)
        
        button_layout.addWidget(self.connect_btn)
        button_layout.addWidget(self.save_config_btn)
        main_layout.addLayout(button_layout)
        
        # Create status display
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)
        
        # Create progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)
        
        # Create separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(separator)
        
        # Create groups section with search and sort
        groups_section = QGroupBox("Select Groups & Channels to Keep:")
        groups_section_layout = QVBoxLayout()
        
        # Search & Sort controls
        search_sort_layout = QHBoxLayout()
        
        # Add search box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search groups...")
        self.search_input.textChanged.connect(self.filter_groups)
        search_sort_layout.addWidget(self.search_input)
        
        # Add filter by type
        type_label = QLabel("Filter by type:")
        self.type_combo = QComboBox()
        self.type_combo.addItems(["All Types", "Groups Only", "Supergroups Only", "Channels Only"])
        self.type_combo.currentIndexChanged.connect(self.filter_groups)
        search_sort_layout.addWidget(type_label)
        search_sort_layout.addWidget(self.type_combo)
        
        groups_section_layout.addLayout(search_sort_layout)
        
        # Create list widget for groups (replaces scroll area with layout)
        self.groups_list = QListWidget()
        self.groups_list.setSelectionMode(QListWidget.NoSelection)  # We use checkboxes instead
        groups_section_layout.addWidget(self.groups_list)
        
        groups_section.setLayout(groups_section_layout)
        main_layout.addWidget(groups_section)
        
        # Create action buttons
        action_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_groups)
        
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self.deselect_all_groups)
        
        self.leave_groups_btn = QPushButton("Leave Unselected Groups")
        self.leave_groups_btn.clicked.connect(self.confirm_leave_groups)
        self.leave_groups_btn.setEnabled(False)
        
        action_layout.addWidget(self.select_all_btn)
        action_layout.addWidget(self.deselect_all_btn)
        action_layout.addWidget(self.leave_groups_btn)
        main_layout.addLayout(action_layout)
        
        self.setCentralWidget(central_widget)
        
    def load_config(self):
        """Load saved API credentials if available"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    lines = f.readlines()
                    if len(lines) >= 3:
                        self.api_id_input.setPlainText(lines[0].strip())
                        self.api_hash_input.setPlainText(lines[1].strip())
                        self.phone_input.setPlainText(lines[2].strip())
            except Exception as e:
                print(f"Error loading config: {e}")
                
    def save_config(self):
        """Save API credentials for future use"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                f.write(f"{self.api_id_input.toPlainText().strip()}\n")
                f.write(f"{self.api_hash_input.toPlainText().strip()}\n")
                f.write(f"{self.phone_input.toPlainText().strip()}\n")
            QMessageBox.information(self, "Success", "Credentials saved successfully")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save credentials: {e}")
            
    def fetch_groups(self):
        """Start worker thread to fetch groups"""
        api_id = self.api_id_input.toPlainText().strip()
        api_hash = self.api_hash_input.toPlainText().strip()
        phone = self.phone_input.toPlainText().strip()
        
        if not api_id or not api_hash or not phone:
            QMessageBox.warning(self, "Missing Information", "Please fill in all API credentials")
            return
            
        self.connect_btn.setEnabled(False)
        self.save_config_btn.setEnabled(False)
        self.status_label.setText("Connecting to Telegram...")
        
        # Clear existing groups
        self.groups_list.clear()
        
        # Start worker thread
        self.worker = TelegramWorker(api_id, api_hash, phone, 'fetch_groups')
        self.worker.update_status.connect(self.update_status)
        self.worker.update_progress.connect(self.update_progress)
        self.worker.fetched_groups.connect(self.display_groups)
        self.worker.operation_complete.connect(self.operation_finished)
        self.worker.start()
        
    def display_groups(self, groups):
        """Display fetched groups with checkboxes in the list widget"""
        self.groups = groups
        
        # Clear existing groups first
        self.groups_list.clear()
        
        # Load saved groups to keep
        groups_to_keep = self.load_groups_to_keep()
        
        # Store original list for filtering
        self.original_groups = groups
        
        # Add groups to the list widget
        self.populate_groups_list(groups, groups_to_keep)
            
        # Enable action buttons
        self.select_all_btn.setEnabled(True)
        self.deselect_all_btn.setEnabled(True)
        self.leave_groups_btn.setEnabled(True)
    
    def populate_groups_list(self, groups, groups_to_keep=None):
        """Populate the list widget with groups"""
        if groups_to_keep is None:
            groups_to_keep = self.load_groups_to_keep()
            
        self.groups_list.clear()
        
        for group in groups:
            group_id = str(group['id'])
            group_name = group['name']
            group_type = group['type']
            
            # Create list item
            item = QListWidgetItem()
            self.groups_list.addItem(item)
            
            # Create widget with checkbox for the item
            item_widget = QWidget()
            layout = QHBoxLayout(item_widget)
            layout.setContentsMargins(5, 2, 5, 2)
            
            checkbox = QCheckBox(f"{group_name} (ID: {group_id}, Type: {group_type})")
            checkbox.setChecked(group_id in groups_to_keep)
            checkbox.setObjectName(f"group_{group_id}")
            
            layout.addWidget(checkbox)
            
            # Set the item's size based on its content
            item.setSizeHint(item_widget.sizeHint())
            
            # Set the widget for the item
            self.groups_list.setItemWidget(item, item_widget)
    
    def filter_groups(self):
        """Filter groups based on search text and selected type"""
        search_text = self.search_input.text().lower()
        type_filter = self.type_combo.currentText()
        
        # First filter by type
        if type_filter == "All Types":
            type_filtered = self.original_groups
        elif type_filter == "Groups Only":
            type_filtered = [g for g in self.original_groups if g['type'] == 'group']
        elif type_filter == "Supergroups Only":
            type_filtered = [g for g in self.original_groups if g['type'] == 'supergroup']
        elif type_filter == "Channels Only":
            type_filtered = [g for g in self.original_groups if g['type'] == 'channel']
        
        # Then filter by search text
        if not search_text:
            filtered_groups = type_filtered
        else:
            # Filter groups based on search text
            filtered_groups = [
                group for group in type_filtered
                if search_text in group['name'].lower() or 
                   search_text in str(group['id'])
            ]
        
        # Re-populate with filtered groups
        self.populate_groups_list(filtered_groups)
        
        # Re-apply current sort
        self.sort_groups(self.sort_combo.currentIndex())
        
    def sort_groups(self, sort_index):
        """Sort groups based on selected sort option"""
        # Get all items from the list
        items = []
        for i in range(self.groups_list.count()):
            item = self.groups_list.item(i)
            widget = self.groups_list.itemWidget(item)
            checkbox = widget.findChild(QCheckBox)
            
            # Extract group info from checkbox text
            text = checkbox.text()
            group_name = text.split(" (ID:")[0]
            group_id = text.split("ID: ")[1].split(",")[0]
            is_checked = checkbox.isChecked()
            
            items.append({
                'name': group_name,
                'id': group_id,
                'checked': is_checked,
                'original_text': text
            })
        
        # Sort based on selected option
        if sort_index == 0:  # Name A-Z
            items.sort(key=lambda x: x['name'])
        elif sort_index == 1:  # Name Z-A
            items.sort(key=lambda x: x['name'], reverse=True)
        elif sort_index == 2:  # ID Low-High
            items.sort(key=lambda x: int(x['id']))
        elif sort_index == 3:  # ID High-Low
            items.sort(key=lambda x: int(x['id']), reverse=True)
            
        # Clear and repopulate list with sorted items
        self.groups_list.clear()
        
        for item_data in items:
            item = QListWidgetItem()
            self.groups_list.addItem(item)
            
            item_widget = QWidget()
            layout = QHBoxLayout(item_widget)
            layout.setContentsMargins(5, 2, 5, 2)
            
            checkbox = QCheckBox(item_data['original_text'])
            checkbox.setChecked(item_data['checked'])
            checkbox.setObjectName(f"group_{item_data['id']}")
            
            layout.addWidget(checkbox)
            
            item.setSizeHint(item_widget.sizeHint())
            self.groups_list.setItemWidget(item, item_widget)
                
    def select_all_groups(self):
        """Select all group checkboxes"""
        for i in range(self.groups_list.count()):
            item = self.groups_list.item(i)
            widget = self.groups_list.itemWidget(item)
            checkbox = widget.findChild(QCheckBox)
            checkbox.setChecked(True)
                
    def deselect_all_groups(self):
        """Deselect all group checkboxes"""
        for i in range(self.groups_list.count()):
            item = self.groups_list.item(i)
            widget = self.groups_list.itemWidget(item)
            checkbox = widget.findChild(QCheckBox)
            checkbox.setChecked(False)
                
    def get_selected_groups(self):
        """Get IDs of selected groups to keep"""
        selected_groups = []
        for i in range(self.groups_list.count()):
            item = self.groups_list.item(i)
            widget = self.groups_list.itemWidget(item)
            checkbox = widget.findChild(QCheckBox)
            
            if checkbox and checkbox.isChecked():
                # Extract group ID from object name or text
                group_id = checkbox.objectName().replace("group_", "")
                if not group_id or group_id == "":
                    # Fallback to parsing from text
                    text = checkbox.text()
                    id_part = text.split("ID: ")[1].split(",")[0]
                    group_id = id_part
                selected_groups.append(group_id)
        return selected_groups
        
    def save_groups_to_keep(self, group_ids):
        """Save IDs of groups to keep to file"""
        try:
            with open(GROUPS_TO_KEEP_FILE, 'w') as f:
                for group_id in group_ids:
                    f.write(f"{group_id}\n")
            return True
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save groups: {e}")
            return False
            
    def load_groups_to_keep(self):
        """Load saved group IDs to keep"""
        groups_to_keep = []
        if os.path.exists(GROUPS_TO_KEEP_FILE):
            try:
                with open(GROUPS_TO_KEEP_FILE, 'r') as f:
                    groups_to_keep = [line.strip() for line in f if line.strip()]
            except Exception as e:
                print(f"Error loading groups to keep: {e}")
        return groups_to_keep
        
    def confirm_leave_groups(self):
        """Confirm before leaving groups"""
        selected_ids = self.get_selected_groups()
        self.save_groups_to_keep(selected_ids)
        
        # Find groups to leave (not in selected_ids)
        groups_to_leave = [group for group in self.groups if str(group['id']) not in selected_ids]
        
        if not groups_to_leave:
            QMessageBox.information(self, "No Action", "No groups to leave. You've selected to keep all groups.")
            return
            
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText(f"You are about to leave {len(groups_to_leave)} groups")
        msg.setInformativeText("This action cannot be undone. Do you want to continue?")
        msg.setWindowTitle("Confirm Action")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        
        if msg.exec_() == QMessageBox.Yes:
            self.leave_groups(groups_to_leave)
            
    def leave_groups(self, groups_to_leave):
        """Start worker thread to leave groups"""
        api_id = self.api_id_input.toPlainText().strip()
        api_hash = self.api_hash_input.toPlainText().strip()
        phone = self.phone_input.toPlainText().strip()
        
        self.leave_groups_btn.setEnabled(False)
        self.select_all_btn.setEnabled(False)
        self.deselect_all_btn.setEnabled(False)
        
        # Start worker thread
        self.worker = TelegramWorker(api_id, api_hash, phone, 'leave_groups', groups_to_leave)
        self.worker.update_status.connect(self.update_status)
        self.worker.update_progress.connect(self.update_progress)
        self.worker.operation_complete.connect(self.operation_finished)
        self.worker.start()
        
    def update_status(self, message):
        """Update status message"""
        self.status_label.setText(message)
        
    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)
        
    def operation_finished(self, success, message):
        """Handle operation completion"""
        if self.worker.action == 'fetch_groups':
            self.connect_btn.setEnabled(True)
            self.save_config_btn.setEnabled(True)
        elif self.worker.action == 'leave_groups':
            self.leave_groups_btn.setEnabled(True)
            self.select_all_btn.setEnabled(True)
            self.deselect_all_btn.setEnabled(True)
            
            if success:
                QMessageBox.information(self, "Operation Complete", message)
            else:
                QMessageBox.warning(self, "Operation Failed", message)

def main():
    app = QApplication(sys.argv)
    window = TelegramGroupManager()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
