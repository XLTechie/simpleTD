import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, List
import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkFont

# ============================================================================
# DATA MODEL
# ============================================================================

@dataclass
class TreeNode:
    """Represents a single node in the tree."""
    id: str
    text: str
    children: List['TreeNode'] = field(default_factory=list)

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'text': self.text,
            'children': [child.to_dict() for child in self.children]
        }

    @classmethod
    def from_dict(cls, data):
        """Create TreeNode from dictionary."""
        children = [cls.from_dict(child) for child in data.get('children', [])]
        return cls(
            id=data['id'],
            text=data['text'],
            children=children
        )


class TreeDataManager:
    """Handles loading and saving tree data to JSON."""
    
    def __init__(self):
        self.app_data_dir = Path(os.getenv('APPDATA')) / 'simpleTD'
        self.file_path = self.app_data_dir / 'simpleTD.json'
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        self.root: Optional[TreeNode] = None
        self.load()

    def load(self):
        """Load tree from JSON file."""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.root = TreeNode.from_dict(data)
            except Exception as e:
                messagebox.showerror("Load Error", f"Failed to load data: {e}")
                self.root = TreeNode(id='root', text='Root', children=[])
        else:
            self.root = TreeNode(id='root', text='Root', children=[])

    def save(self):
        """Save tree to JSON file."""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.root.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save data: {e}")

    def find_node_by_id(self, node_id: str, node: Optional[TreeNode] = None) -> Optional[TreeNode]:
        """Find a node by its ID."""
        if node is None:
            node = self.root
        
        if node.id == node_id:
            return node
        
        for child in node.children:
            result = self.find_node_by_id(node_id, child)
            if result:
                return result
        return None

    def find_parent_by_child_id(self, child_id: str, node: Optional[TreeNode] = None) -> Optional[TreeNode]:
        """Find the parent of a node by its child's ID."""
        if node is None:
            node = self.root
        
        for child in node.children:
            if child.id == child_id:
                return node
        
        for child in node.children:
            result = self.find_parent_by_child_id(child_id, child)
            if result:
                return result
        return None


# ============================================================================
# GUI APPLICATION
# ============================================================================

class TreeViewApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple Tree Editor")
        self.root.geometry("600x500")
        
        self.data_manager = TreeDataManager()
        self.clipboard = None  # For cut/copy: (node_data, operation_type)
        self.next_id_counter = 1
        
        self._setup_ui()
        self._load_tree_to_widget()
        self._bind_keys()
        
        # Save on exit
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_ui(self):
        """Set up the user interface."""
        # Create a frame for the tree view
        frame = ttk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create the tree view
        self.tree = ttk.Treeview(frame, height=20)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscroll=scrollbar.set)
        
        # Bind right-click for context menu
        self.tree.bind("<Button-3>", self._show_context_menu)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, padx=5, pady=2)

    def _load_tree_to_widget(self):
        """Load the data tree into the treeview widget."""
        self.tree.delete(*self.tree.get_children())
        self._insert_nodes(self.data_manager.root.children, '')

    def _insert_nodes(self, nodes: List[TreeNode], parent_id: str):
        """Recursively insert nodes into the treeview."""
        for node in nodes:
            item_id = self.tree.insert(parent_id, 'end', iid=node.id, text=node.text)
            if node.children:
                self._insert_nodes(node.children, item_id)

    def _bind_keys(self):
        """Bind keyboard shortcuts."""
        self.tree.bind('<Left>', self._on_collapse)
        self.tree.bind('<Right>', self._on_expand)
        self.tree.bind('<Control-n>', self._on_insert_sibling)
        self.tree.bind('<Control-Shift-n>', self._on_insert_child)
        self.tree.bind('<Delete>', self._on_delete)
        self.tree.bind('<Control-c>', self._on_copy)
        self.tree.bind('<Control-x>', self._on_cut)
        self.tree.bind('<Control-v>', self._on_paste)

    def _get_selected_item(self) -> Optional[str]:
        """Get the currently selected item ID."""
        selection = self.tree.selection()
        return selection[0] if selection else None

    def _on_collapse(self, event):
        """Collapse the selected item."""
        item_id = self._get_selected_item()
        if item_id:
            self.tree.item(item_id, open=False)

    def _on_expand(self, event):
        """Expand the selected item."""
        item_id = self._get_selected_item()
        if item_id:
            self.tree.item(item_id, open=True)

    def _on_insert_sibling(self, event):
        """Insert a new sibling at the same level (Insert key)."""
        item_id = self._get_selected_item()
        # If nothing is selected, add to root level
        if not item_id:
            parent_node = self.data_manager.root
        else:
            parent_node = self.data_manager.find_parent_by_child_id(item_id)
            if not parent_node:
                messagebox.showerror("Error", "Cannot find parent node.")
                return

        text = self._ask_for_text("Add New Item", "Enter item text:")
        if text:
            new_node = TreeNode(
                id=f"node_{self.next_id_counter}",
                text=text,
                children=[]
            )
            self.next_id_counter += 1
        
            if item_id:
                # Insert after the selected item
                current_index = parent_node.children.index(
                    self.data_manager.find_node_by_id(item_id)
                )
                parent_node.children.insert(current_index + 1, new_node)
            else:
                # No selection: append to root
                parent_node.children.append(new_node)
        
            self.data_manager.save()
            self._load_tree_to_widget()
            self.status_var.set(f"Added new item: {text}")

    def _on_insert_child(self, event):
        """Insert a child under the selected item (Shift+Insert)."""
        item_id = self._get_selected_item()
        if not item_id:
            messagebox.showinfo("Info", "Please select an item first.")
            return
        
        parent_node = self.data_manager.find_node_by_id(item_id)
        if not parent_node:
            messagebox.showerror("Error", "Cannot find node.")
            return
        
        text = self._ask_for_text("Add New Child", "Enter child item text:")
        if text:
            new_node = TreeNode(
                id=f"node_{self.next_id_counter}",
                text=text,
                children=[]
            )
            self.next_id_counter += 1
            parent_node.children.append(new_node)
            
            self.data_manager.save()
            self._load_tree_to_widget()
            
            # Expand the parent to show the new child
            self.tree.item(item_id, open=True)
            self.status_var.set(f"Added child: {text}")

    def _on_delete(self, event):
        """Delete the selected item."""
        item_id = self._get_selected_item()
        if not item_id:
            messagebox.showinfo("Info", "Please select an item to delete.")
            return
        
        if item_id == 'root':
            messagebox.showwarning("Warning", "Cannot delete the root node.")
            return
        
        if messagebox.askyesno("Confirm Delete", "Delete this item and all its children?"):
            parent_node = self.data_manager.find_parent_by_child_id(item_id)
            if parent_node:
                node_to_delete = self.data_manager.find_node_by_id(item_id)
                parent_node.children.remove(node_to_delete)
                self.data_manager.save()
                self._load_tree_to_widget()
                self.status_var.set("Item deleted.")

    def _on_copy(self, event):
        """Copy the selected item."""
        item_id = self._get_selected_item()
        if not item_id:
            messagebox.showinfo("Info", "Please select an item to copy.")
            return
        
        node = self.data_manager.find_node_by_id(item_id)
        if node:
            self.clipboard = (node, 'copy')
            self.status_var.set(f"Copied: {node.text}")

    def _on_cut(self, event):
        """Cut the selected item."""
        item_id = self._get_selected_item()
        if not item_id:
            messagebox.showinfo("Info", "Please select an item to cut.")
            return
        
        if item_id == 'root':
            messagebox.showwarning("Warning", "Cannot cut the root node.")
            return
        
        node = self.data_manager.find_node_by_id(item_id)
        if node:
            self.clipboard = (node, 'cut')
            self.status_var.set(f"Cut: {node.text}")

    def _on_paste(self, event):
        """Paste the clipboard item under the selected item."""
        if not self.clipboard:
            messagebox.showinfo("Info", "Nothing to paste. Copy or cut an item first.")
            return
        
        target_id = self._get_selected_item()
        if not target_id:
            messagebox.showinfo("Info", "Please select a target location.")
            return
        
        target_node = self.data_manager.find_node_by_id(target_id)
        if not target_node:
            messagebox.showerror("Error", "Cannot find target node.")
            return
        
        clipboard_node, operation = self.clipboard
        
        if operation == 'cut':
            # Remove from original location
            parent = self.data_manager.find_parent_by_child_id(clipboard_node.id)
            if parent:
                parent.children.remove(clipboard_node)
            self.clipboard = None
        else:  # copy
            # Deep copy the node
            import copy
            clipboard_node = copy.deepcopy(clipboard_node)
            # Reassign IDs to avoid conflicts
            self._reassign_ids(clipboard_node)
        
        # Add to target
        target_node.children.append(clipboard_node)
        self.data_manager.save()
        self._load_tree_to_widget()
        self.tree.item(target_id, open=True)
        self.status_var.set("Pasted successfully.")

    def _reassign_ids(self, node: TreeNode):
        """Recursively reassign IDs to avoid conflicts."""
        node.id = f"node_{self.next_id_counter}"
        self.next_id_counter += 1
        for child in node.children:
            self._reassign_ids(child)

    def _ask_for_text(self, title: str, prompt: str) -> Optional[str]:
        """Simple dialog to ask for text input."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("300x100")
        dialog.transient(self.root)
        dialog.grab_set()
        
        label = ttk.Label(dialog, text=prompt)
        label.pack(padx=10, pady=10)
        
        entry = ttk.Entry(dialog, width=40)
        entry.pack(padx=10, pady=5)
        entry.focus()
        
        result = [None]
        
        def on_ok():
            result[0] = entry.get().strip()
            if not result[0]:
                messagebox.showwarning("Warning", "Please enter some text.")
                return
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        ok_button = ttk.Button(button_frame, text="OK", command=on_ok)
        ok_button.pack(side=tk.LEFT, padx=5)
        
        cancel_button = ttk.Button(button_frame, text="Cancel", command=on_cancel)
        cancel_button.pack(side=tk.LEFT, padx=5)
        
        dialog.wait_window()
        return result[0]

    def _show_context_menu(self, event):
        """Show right-click context menu."""
        item_id = self.tree.identify('item', event.x, event.y)
        if not item_id:
            return
        
        self.tree.selection_set(item_id)
        
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="Add Sibling (Ctrl+N)", command=lambda: self._on_insert_sibling(None))
        menu.add_command(label="Add Child (Ctrl+Shift+N)", command=lambda: self._on_insert_child(None))
        menu.add_separator()
        menu.add_command(label="Copy (Ctrl+C)", command=lambda: self._on_copy(None))
        menu.add_command(label="Cut (Ctrl+X)", command=lambda: self._on_cut(None))
        menu.add_command(label="Paste (Ctrl+V)", command=lambda: self._on_paste(None))
        menu.add_separator()
        menu.add_command(label="Delete (Del)", command=lambda: self._on_delete(None))
        
        menu.post(event.x_root, event.y_root)

    def _on_closing(self):
        """Handle window closing."""
        self.data_manager.save()
        self.root.destroy()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    root = tk.Tk()
    app = TreeViewApp(root)
    root.mainloop()
