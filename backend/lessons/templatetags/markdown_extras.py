"""
Custom template tags for markdown rendering.
"""
import markdown as md
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='markdown')
def markdown_filter(text):
    """
    Convert markdown text to HTML.
    
    Usage in template:
        {{ qa.answer|markdown }}
    """
    if not text:
        return ""
    
    # Configure markdown with extensions for better formatting
    html = md.markdown(
        text,
        extensions=[
            'fenced_code',  # Support ```code blocks```
            'nl2br',        # Convert newlines to <br>
            'tables',       # Support tables
            'sane_lists',   # Better list handling
        ]
    )
    
    return mark_safe(html)
