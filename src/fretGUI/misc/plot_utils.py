"""
Utility functions for matplotlib plots.
"""


def enable_legend_toggle(ax, picker_tolerance=5, connection_id_attr='_legend_toggle_cid'):
    """
    Enable click-to-toggle functionality on legend lines for a matplotlib axes.
    
    When a legend line is clicked, the corresponding plot line will be toggled
    between visible and hidden. Hidden lines will have their legend entry
    shown with reduced alpha (0.2).
    
    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axes object containing the plot and legend
    picker_tolerance : int, optional
        Tolerance in points for picking legend lines (default: 5)
    connection_id_attr : str, optional
        Attribute name to store connection ID on the figure canvas (default: '_legend_toggle_cid')
        This allows disconnecting previous handlers when called multiple times.
    
    Returns
    -------
    int
        Connection ID for the pick event handler. Can be used to disconnect later.
    
    Notes
    -----
    The legend must already exist on the axes before calling this function.
    If called multiple times on the same figure, previous handlers will be
    automatically disconnected.
    
    Example
    -------
    >>> import matplotlib.pyplot as plt
    >>> fig, ax = plt.subplots()
    >>> line1, = ax.plot([1, 2, 3], [1, 2, 3], label='Line 1')
    >>> line2, = ax.plot([1, 2, 3], [3, 2, 1], label='Line 2')
    >>> ax.legend()
    >>> enable_legend_toggle(ax)
    >>> plt.show()
    """
    legend = ax.get_legend()
    if legend is None:
        raise ValueError("No legend found on axes. Create a legend first using ax.legend()")
    
    # Get all lines from the axes that have labels
    lines_with_labels = [line for line in ax.lines if line.get_label() and line.get_label() != '_nolegend_']
    patches_with_labels = [patch for patch in ax.patches if patch.get_label() and patch.get_label() != '_nolegend_']
    collections_with_labels = [col for col in ax.collections if col.get_label() and col.get_label() != '_nolegend_']
    
    # Combine all labeled artists
    labeled_artists = lines_with_labels + patches_with_labels + collections_with_labels
    
    if not labeled_artists:
        raise ValueError("No labeled artists found on axes. Add labels to your plot elements.")
    
    # Get legend lines (proxy artists)
    legend_lines = legend.get_lines()
    
    if len(legend_lines) != len(labeled_artists):
        raise ValueError(
            f"Mismatch between legend entries ({len(legend_lines)}) and labeled artists ({len(labeled_artists)}). "
            "Make sure all plot elements have unique labels."
        )
    
    # Map legend lines to original plot lines
    map_legend_to_artist = {}
    for legend_line, artist in zip(legend_lines, labeled_artists):
        legend_line.set_picker(picker_tolerance)
        map_legend_to_artist[legend_line] = artist
    
    # Event handler function
    def on_pick(event):
        legend_line = event.artist
        
        # Check if the picked artist is in our mapping
        if legend_line not in map_legend_to_artist:
            return  # Ignore picks on other elements
        
        artist = map_legend_to_artist[legend_line]
        
        # Toggle visibility
        visible = not artist.get_visible()
        artist.set_visible(visible)
        
        # Change the legend line alpha to indicate state
        if visible:
            legend_line.set_alpha(1.0)
        else:
            legend_line.set_alpha(0.2)
        
        # Redraw the figure
        ax.figure.canvas.draw()
    
    # Disconnect any existing handler to avoid duplicates
    canvas = ax.figure.canvas
    if hasattr(canvas, connection_id_attr):
        old_cid = getattr(canvas, connection_id_attr)
        canvas.mpl_disconnect(old_cid)
    
    # Connect the event handler and store the connection ID
    cid = canvas.mpl_connect('pick_event', on_pick)
    setattr(canvas, connection_id_attr, cid)
    
    return cid


def disable_legend_toggle(ax, connection_id_attr='_legend_toggle_cid'):
    """
    Disable the legend toggle functionality for an axes.
    
    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axes object
    connection_id_attr : str, optional
        Attribute name where connection ID is stored (default: '_legend_toggle_cid')
    
    Returns
    -------
    bool
        True if a handler was disconnected, False if none was found
    """
    canvas = ax.figure.canvas
    if hasattr(canvas, connection_id_attr):
        cid = getattr(canvas, connection_id_attr)
        canvas.mpl_disconnect(cid)
        delattr(canvas, connection_id_attr)
        return True
    return False


