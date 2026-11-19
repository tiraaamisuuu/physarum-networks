"""Full-rate scalar measurements, distinct from sparse spatial snapshots."""
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg,NavigationToolbar2QT
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel


def envelope(time,values,bins=800):
    """Keep every sample in a bin mean and extrema; never decimate away peaks."""
    time=np.asarray(time);values=np.asarray(values)
    if len(time)!=len(values) or len(time)==0:raise ValueError('Invalid measurement series.')
    chunks=np.array_split(np.arange(len(time)),min(bins,len(time)))
    return tuple(np.array([fn(i) for i in chunks]) for fn in (lambda i:time[i].mean(),lambda i:values[i].mean(),lambda i:values[i].min(),lambda i:values[i].max()))


class BiologyMeasures(QWidget):
    def __init__(self):
        super().__init__();layout=QVBoxLayout(self);caption=QLabel('Conductivity-derived measures are recorded every integration step. The plots retain bin means and min–max envelopes, so sparse growth frames cannot hide fast changes. Volume is the proxy Σ length × √D, with uncalibrated units; it is not conserved organism biomass.');caption.setWordWrap(True);layout.addWidget(caption)
        self.figure=Figure(figsize=(10,7),layout='constrained',facecolor='#fbfcf9');self.canvas=FigureCanvasQTAgg(self.figure);layout.addWidget(NavigationToolbar2QT(self.canvas,self));layout.addWidget(self.canvas,1);self.axes=[];self.cursors=[];self.run=None
    def setup(self,run):
        self.run=run;self.figure.clear();self.axes=[];self.cursors=[];g=run.get('global_history')
        if g is None:self.figure.text(.5,.5,'This earlier record has no full-rate global series.\nRecompute to measure the changing vein network at every step.',ha='center',va='center');self.canvas.draw_idle();return
        for row,key,title,unit,color in [(1,'vein_volume','Conductivity-derived volume proxy','Σ ℓ√D (model units)','#356b50'),(2,'retained_length_D1','Retained vein length · D ≥ 1','Length (model units)','#a87838')]:
            ax=self.figure.add_subplot(2,1,row);t,mean,low,high=envelope(g['time'],g[key]);ax.fill_between(t,low,high,color=color,alpha=.18,label='Min–max within each bin');ax.plot(t,mean,color=color,lw=1,label='Bin mean');ax.set(xlabel='Model time',ylabel=unit,xlim=(g['time'][0],g['time'][-1]));ax.set_title(title,loc='left',fontsize=11);ax.spines[['top','right']].set_visible(False);ax.tick_params(labelsize=8);ax.grid(alpha=.15);ax.legend(fontsize=8,frameon=False);self.axes.append(ax);self.cursors.append(ax.axvline(0,color='#555',ls='--',lw=.8))
        self.canvas.draw_idle()
    def display(self,time):
        for cursor in self.cursors:cursor.set_xdata([time,time])
        if self.cursors:self.canvas.draw_idle()
