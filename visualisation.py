import pandas as pd
import plotly.graph_objects as go

def plot_histogram(data, time_frame):
    df = pd.DataFrame(data, columns=['date', 'resources', 'email', 'phone', 'name'])
    df['date'] = pd.to_datetime(df['date'])
    
    # Time grouping based on the time frame
    if time_frame == 'day':
        df = df.groupby(df['date'].dt.hour).sum()
    elif time_frame == 'month':
        df = df.groupby(df['date'].dt.day).sum()
    else:
        df = df.groupby(df['date'].dt.date).sum()

    fig = go.Figure(data=go.Histogram(x=df.index, y=df['resources']))
    fig.show()
