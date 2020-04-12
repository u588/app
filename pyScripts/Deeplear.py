import pandas
import numpy
from keras.layers.core import Dense, Activation, Dropout
from keras.layers.recurrent import LSTM
from keras.models import Sequential
import matplotlib.pyplot as plt

CONST_TRAINING_SEQUENCE_LENGTH = 60
CONST_TESTING_CASES = 5

def dataNormalization(data):
	return [(datum-data[0])/data[0] for datum in data]

def dataDeNormaliztion(date, base):
	return [(datum+1)*base for datum in data]

def getDeepLearningData(ticker):
   #文件存储位置
	data = pandas.read_csv('F:/QutData/'+ticker+'.csv')['close'].tolist()
	dataTraining = []
	for i in range(len(data)-CONST_TESTING_CASES*CONST_TRAINING_SEQUENCE_LENGTH):
		dataSegment = data[i:i+CONST_TRAINING_SEQUENCE_LENGTH+1]
		dataTraining.append(dataNormalization(dataSegment))
	
	dataTraining = numpy.array(dataTraining)
	numpy.random.shuffle(dataTraining)
	X_Training = dataTraining[:, :-1]
	Y_Training = dataTraining[:, -1]

	X_Testing = []
	Y_Testing_Base = []



	for i in range(CONST_TESTING_CASES, 0, -1):
		dataSegment = data[-(i+1)*CONST_TRAINING_SEQUENCE_LENGTH:-i*CONST_TRAINING_SEQUENCE_LENGTH]
		Y_Testing_Base.append(dataSegment[0])
		X_Testing.append(dataNormalization(dataSegment))

	Y_Testing = data[-CONST_TESTING_CASES*CONST_TRAINING_SEQUENCE_LENGTH:]

	X_Testing = numpy.array(X_Testing)
	Y_Testing = numpy.array(Y_Testing)

	X_Training = numpy.reshape(X_Training, (X_Training.shape[0], X_Training.shape[1], 1))
   #X_Testing = numpy.reshape(X_Testing, (X_Testing.shape[0], X_Testing.shape[1], 1))
	print('X_Testing')
	print(X_Testing)
	return X_Training, Y_Training, X_Testing, Y_Testing, Y_Testing_Base

def predict(models, X):
	predictionsNormalized = []
	for i in range(len(X)):
		data = X[i]
		result = []

		for j in range(CONST_TRAINING_SEQUENCE_LENGTH):
			predicted = models.predict(data[numpy.newaxis, :, :])[0,0]
			result.append(predicted)
			data = data[1:]
			data = numpy.insert(data, [CONST_TRAINING_SEQUENCE_LENGTH-1], predicted, axis=0)

		predictionsNormalized.append(result)
		return predictionsNormalized

def plotResults(Y_Hot, Y):
	plt.plot(Y)
	for i in range(len(Y_Hat)):
		padding = [None for _ in range(i*CONST_TRAINING_SEQUENCE_LENGTH)]
		plt.plot(padding+Y_Hat[i])

	plt.show()

def predictLSTM(ticker):
	X_Training, Y_Training, X_Testing, Y_Testing, Y_Testing_Base = getDeepLearningData(ticker)

	models = Sequential()

	models.add(LSTM(
		input_dim = 1,
		output_dim = 50,
		return_sequences=True))

	models.add(Dropout(0.2))

	models.add(LSTM(
		200,
		return_sequences=False))
	models.add(Dropout(0.2))

	models.add(Dense(output_dim=1))
	models.add(Activation('linear'))

	models.compile(loss='mse',optimizer='rmsprop')

	models.fit(X_Training, Y_Training,
		batch_size=512,
		nb_epoch=5,
		validation_split=0.05)

	predictionsNormalized = predict(models,X_Testing)

	predictions = []
	for i, row in enumerate(predictionsNormalized):
		predictions.append(dataDeNormaliztion(row,Y_Testing_Base[i]))

	plotResults(predictions,Y_Testing)

predictLSTM(ticker='601989')

