import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

x_data = np.random.rand(100).astype(np.float32)
y_data = x_data*0.1 + 0.3

Weighits = tf.Variable(tf.random_uniform([1], -1.0, 1.0))
biases = tf.Variable(tf.zeros([1]))

y = Weighits*x_data + biases
loss = tf.reduce_mean(tf.square(y-y_data))
optimizer = tf.train.GradientDescentOptimizer(0.5)
train = optimizer.minimize(loss)

#initialize_all_variables is deprecated and will be removed after 2017-03-02.
#init = tf.initialize_all_variables()

init = tf.global_variables_initializer()
sess = tf.Session()
#writer = tf.train.SummaryWriter("logs", sess.graph)
writer = tf.summary.FileWriter("F:/QutData/logs", sess.graph)
sess.run(init)

#df = pd.DataFrame(columns=['step', 'Weighits', 'biases'])

for step in range(10):
	sess.run(train)

#	seri = pd.Series([step,sess.run(Weighits), sess.run(biases)],index=['step', 'Weighits', 'biases'])
#	print(seri)
#	df = pd.concat([df, np.array([step,sess.run(Weighits), sess.run(biases)]).reshape((1,3))])
#	df = df.append(seri,ignore_index=True)

	if step %20 == 0:
		print(step, sess.run(Weighits), sess.run(biases))
#		df = pd.concat([df, pd.Series([step,sess.run(Weighits), sess.run(biases)]).reshape(1,3)])
		#dd = pd.concat([dd,df])


#print(df)
#df.plot()
#plt.show()
#plt(dd)
#plt.show()