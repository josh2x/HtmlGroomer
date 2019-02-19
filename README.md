# HtmlGroomer for Sublime Text

## About

HtmlGroomer standardizes and grooms your HTML email code. Specifically:

* Clean indentation of elements per DOM hierarchy
* Stardardized order of HTML tag attributes. Order can be adjusted in plugin settings.
* Stardardized order of inline CSS properties. Order can be adjusted in plugin settings.
* Ensure all HTML attributes with values are double quoted
* Ensure void elements are self closing tags in XHTML documents
* Ensure boolean attributes have values to match the spec in XHTML documents
* HTML elements with height and width attributes defined in px will be corrected
* Hex colors will formated in uppercase. Shorthand hex colors will be expanded if expand_hexcolors flag is set in the plugin settings.

Additionally, these items will addressed in HTML emails:

* Where width is set in an HTML attribute it will be added as an inline CSS property to correct rendering in Outlook 120dpi
* All image tags will have border and alt attributes
* Movable Ink images with empty alt attributes will have default alt text. Default can be defined in the plugin settings.

## Plugin Usage

Press <kbd>ctrl</kbd>+<kbd>alt</kbd>+<kbd>h</kbd> or open "Tools" menu and select "HtmlGroomer > HTML".
Press <kbd>ctrl</kbd>+<kbd>shift</kbd>+<kbd>h</kbd> or open "Tools" menu and select "HtmlGroomer > HTML Email".

## Default Settings

    "indent_unit": "\t",
    "break_unit": "\n",
    "tab_size": 4,
    "force_xhtml": false,
    "expand_hexcolors": true,
    "use_native_indent": false,
    "format_css": true,
    "merge_percent_width": false,
    "movable_ink_alt": "Display images to see real-time content.",
    "keep_inner_whitespace": [
        "style",
        "script",
        ],
    "double_break_before": [
        ],
    "double_break_after": [
        "br",
         ],
    "delete_tags": [
        "tbody",
         ],
    "dont_increase_indent": [
        "html",
        "table",
        "custom",
        ],

## Authors

Joshua McFarren