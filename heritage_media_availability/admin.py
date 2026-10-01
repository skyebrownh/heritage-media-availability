"""
Django admin setup: the screens Skye uses to manage the roster (AD-2).

Django builds the add/edit/list pages for us from the model; this file only
chooses which columns, filters and actions appear.
"""

from django.contrib import admin

from .models import Member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    """Roster screen: add people, fix names, and switch them active or inactive."""

    list_display = ['first_name', 'last_name', 'is_active', 'created_at']
    # Clicking a name opens that person's edit page.
    list_display_links = ['first_name', 'last_name']
    # AD-2: tick or untick "active" right in the list, then press Save,
    # without opening each person's page.
    list_editable = ['is_active']
    list_filter = ['is_active']
    search_fields = ['first_name', 'last_name']
    # The edit page only needs the fields Skye can change; created_at is automatic.
    fields = ['first_name', 'last_name', 'is_active']

    def has_delete_permission(self, request, obj=None):
        """
        AD-2: no hard delete in v1.

        Returning False removes the Delete button, the delete page, and the
        bulk "Delete selected" action, even for a superuser. Deleting a member
        would also wipe their submission history, which the spec says to keep.
        """
        return False
