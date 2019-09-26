
import sys
import sklearn
from sklearn.metrics import precision_score
from sklearn.metrics import recall_score
from sklearn.metrics import roc_auc_score
from sklearn.metrics import f1_score
from sklearn.metrics import confusion_matrix
from sklearn.metrics import roc_curve
from sklearn.metrics import auc
import scipy.io as sio
import os
import pandas as pd
import pickle
import tensorflow as tf
import numpy as np
import time
import math


conv_fuse = "plus"
# final_fuse = "concat+pointwise_conv"
# final_fuse = "concat+fc"
# final_fuse = "concat"
# final_fuse = "add"

conv_1_shape = '4*4*1*4'
# conv_2_shape = 'None'
conv_2_shape = '4*4*1*8'
# conv_3_shape = 'None'
conv_3_shape = '4*4*1*16'
# conv_4_shape = 'None'
conv_4_shape = '1*1*1*4'

window_size = 128
# convolution full connected parameter
fc_size = 1024

dropout_prob = 0.5
np.random.seed(32)

calibration = 'N'
norm_type = '2D'
regularization_method = 'dropout'
enable_penalty = True

cnn_suffix      =".mat_win_128_cnn_dataset.pkl"
label_suffix    =".mat_win_128_labels.pkl"

data_file   =sys.argv[1]
arousal_or_valence  =sys.argv[2]

dataset_dir = "/home/yyl/deap_shuffled_data/"+arousal_or_valence+"/"
###load training set



with open(dataset_dir + data_file + cnn_suffix, "rb") as fp:
    cnn_datasets = pickle.load(fp)
with open(dataset_dir + data_file + label_suffix, "rb") as fp:
    labels = pickle.load(fp)
    labels = np.transpose(labels)

lables_backup = labels

cnn_datasets = cnn_datasets.reshape(len(cnn_datasets), window_size, 9,9, 1)
one_hot_labels = np.array(list(pd.get_dummies(labels)))
#print("one_hot_labels:",train_labels.shape)
labels = np.asarray(pd.get_dummies(labels), dtype=np.int8)
# shuffle data

index = np.array(range(0, len(labels)))
np.random.shuffle( index)

cnn_datasets   = cnn_datasets[index]
labels  = labels[index]

print("**********(" + time.asctime(time.localtime(time.time())) + ") Load and Split dataset End **********\n")

print(
    "**********(" + time.asctime(time.localtime(time.time())) + ") Define parameters and functions Begin: **********\n")

# input parameter
n_input_ele = 32
n_time_step = window_size

input_channel_num = 1
input_height = 9
input_width = 9

n_labels = 2

# training parameter
lambda_loss_amount = 0.5
training_epochs = 80

batch_size = 200


# kernel parameter
kernel_height_1st = 4
kernel_width_1st = 4

kernel_height_2nd = 4
kernel_width_2nd = 4

kernel_height_3rd = 4
kernel_width_3rd = 4

kernel_height_4th = 1
kernel_width_4th = 1

kernel_depth_5th    = window_size
kernel_height_5th   = 1
kernel_width_5th    = 1

kernel_depth_6th    = 4
kernel_height_6th   = 4
kernel_width_6th    = 4

kernel_depth_7th    = 4
kernel_height_7th   = 4
kernel_width_7th    = 4

kernel_stride = 1
conv_channel_num = 8

# pooling parameter
pooling_height = 2
pooling_width = 2
pooling_stride = 2
# algorithn parameter
learning_rate = 1e-4

def weight_variable(shape,name):
    initial = tf.truncated_normal(shape, stddev=0.1)
    return tf.Variable(initial,name=name)

def bias_variable(shape,name):
    initial = tf.constant(0.1, shape=shape)
    return tf.Variable(initial,name=name)

def conv1d(x, W, kernel_stride):
    # API: must strides[0]=strides[4]=1
    return tf.nn.conv1d(x, W, stride=kernel_stride, padding='SAME')

def conv2d(x, W, kernel_stride):
    # API: must strides[0]=strides[4]=1
    return tf.nn.conv2d(x, W, strides=[1, kernel_stride, kernel_stride, 1], padding='SAME')

def conv3d(x, W, kernel_stride,):
    # API: must strides[0]=strides[4]=1
    return tf.nn.conv3d(x, W, strides=[1, kernel_stride, kernel_stride, kernel_stride, 1], padding='SAME')

def apply_conv1d(x, filter_width, in_channels, out_channels, kernel_stride,name):
    weight = weight_variable([filter_width, in_channels, out_channels],name)
    bias = bias_variable([out_channels],name)  # each feature map shares the same weight and bias
    return tf.nn.elu(tf.add(conv1d(x, weight, kernel_stride), bias))

def apply_conv2d(x, filter_height, filter_width, in_channels, out_channels, kernel_stride,name):
    weight = weight_variable([filter_height, filter_width, in_channels, out_channels],name)
    bias = bias_variable([out_channels],name)  # each feature map shares the same weight and bias
    print("weight shape:", np.shape(weight))
    print("x shape:", np.shape(x))
    #tf.layers.batch_normalization()
    return tf.nn.selu(tf.layers.batch_normalization(conv2d(x, weight, kernel_stride)))

def apply_conv3d(x, filter_depth, filter_height, filter_width, in_channels, out_channels, kernel_stride,name):
    weight = weight_variable([filter_depth, filter_height, filter_width, in_channels, out_channels],name)
    bias = bias_variable([out_channels],name) # each feature map shares the same weight and bias
    print("weight shape:", np.shape(weight))
    print("x shape:", np.shape(x))
    conv_3d = tf.add(conv3d(x, weight, kernel_stride), bias)
    return tf.nn.selu(conv_3d)

def apply_max_pooling(x, pooling_height, pooling_width, pooling_stride):
    # API: must ksize[0]=ksize[4]=1, strides[0]=strides[4]=1
    return tf.nn.max_pool(x, ksize=[1, pooling_height, pooling_width, 1],
                          strides=[1, pooling_stride, pooling_stride, 1], padding='SAME')

def apply_fully_connect(x, x_size, fc_size,name):
    fc_weight = weight_variable([x_size, fc_size],name)
    fc_bias = bias_variable([fc_size],name)
    return tf.nn.selu(tf.add(tf.matmul(x, fc_weight), fc_bias))

def apply_readout(x, x_size, readout_size,name):
    readout_weight = weight_variable([x_size, readout_size],name)
    readout_bias = bias_variable([readout_size],name)
    return tf.add(tf.matmul(x, readout_weight), readout_bias)

print("\n**********(" + time.asctime(time.localtime(time.time())) + ") Define parameters and functions End **********")

print("\n**********(" + time.asctime(time.localtime(time.time())) + ") Define NN structure Begin: **********")

# input placeholder
cnn_in = tf.placeholder(tf.float32, shape=[None, input_height, input_width, input_channel_num], name='cnn_in')
Y = tf.placeholder(tf.float32, shape=[None, n_labels], name='Y')
keep_prob = tf.placeholder(tf.float32, name='keep_prob')
phase_train = tf.placeholder(tf.bool, name='phase_train')

###########################################################################################
# add cnn parallel to network
###########################################################################################
# first CNN layer
conv_1 = apply_conv2d(cnn_in, kernel_height_1st, kernel_width_1st, input_channel_num, conv_channel_num, kernel_stride,'conv1')
# pool_1 = apply_max_pooling(conv_1, pooling_height, pooling_width, pooling_stride)
print("conv_1 shape:", conv_1.shape)
print("\n")
# second CNN layer
conv_2 = apply_conv2d(conv_1, kernel_height_2nd, kernel_width_2nd, conv_channel_num, conv_channel_num * 2, kernel_stride,'conv2')
# pool_2 = apply_max_pooling(conv_2, pooling_height, pooling_width, pooling_stride)
print("conv_2 shape:", conv_2.shape)
print("\n")
# third CNN layer
conv_3 = apply_conv2d(conv_2, kernel_height_3rd, kernel_width_3rd, conv_channel_num * 2, conv_channel_num * 4, kernel_stride,'conv3')
print("conv_3 shape:", conv_3.shape)
print("\n")

conv_4 = apply_conv2d(conv_3,kernel_height_4th, kernel_width_4th,conv_channel_num * 4,1,kernel_stride,"conv4")
print("conv_4 shape:", conv_4.shape)
print("\n")
shape = conv_4.get_shape().as_list()
cubic = tf.reshape(conv_4,[-1,window_size,9,9,1])
print("cubic shape:", cubic.shape)
print("\n")
conv_5 = apply_conv3d(cubic, kernel_depth_5th, kernel_height_5th, kernel_width_5th, input_channel_num, conv_channel_num, kernel_stride,'conv5')
# pool_1 = cnn_3d.apply_max_pooling3d(conv_1, pooling_depth, pooling_height, pooling_width, pooling_stride)
print("conv5 shape:",conv_5.shape)
print("\n")
# second CNN layer
conv_6 = apply_conv3d(conv_5, kernel_depth_6th, kernel_height_6th, kernel_width_6th, conv_channel_num, conv_channel_num*2, kernel_stride,'conv6')
print("conv6 shape:",conv_6.shape)
print("\n")
# pool_2 = cnn_3d.apply_max_pooling3d(conv_2, pooling_depth, pooling_height, pooling_width, pooling_stride)
# third CNN layer
conv_7 = apply_conv3d(conv_6, kernel_depth_7th, kernel_height_7th, kernel_width_7th, conv_channel_num *2, conv_channel_num *4, kernel_stride,'conv7')
print("conv7 shape:",conv_7.shape)
print("\n")
#conv_5 = 
# fully connected layer

shape = conv_7.get_shape().as_list()
conv_7_flat = tf.reshape(conv_7, [-1, shape[1] * shape[2] * shape[3] * shape[4]])
cnn_fc = apply_fully_connect(conv_7_flat, shape[1] * shape[2] * shape[3] * shape[4], fc_size,"fc")
print("shape after cnn_full", np.shape(cnn_fc))
# dropout regularizer
# Dropout (to reduce overfitting; useful when training very large neural network)
# We will turn on dropout during training & turn off during testing
fc_drop = tf.nn.dropout(cnn_fc, keep_prob)

# readout layer
y_ = apply_readout(fc_drop, fc_size, n_labels,'readout')
y_pred = tf.argmax(tf.nn.softmax(y_), 1, name="y_pred")
y_posi = tf.nn.softmax(y_, name="y_posi")

# l2 regularization
l2 = lambda_loss_amount * sum(
    tf.nn.l2_loss(tf_var) for tf_var in tf.trainable_variables()
)

if enable_penalty:
    # cross entropy cost function
    cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=y_, labels=Y) + l2, name='loss')
else:
    # cross entropy cost function
    cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=y_, labels=Y), name='loss')

optimizer = tf.train.AdamOptimizer(learning_rate).minimize(cost)

# get correctly predicted object and accuracy
correct_prediction = tf.equal(tf.argmax(tf.nn.softmax(y_), 1), tf.argmax(Y, 1))
accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32), name='accuracy')

#tf.summary.scalar('accuracy',accuracy)

print("\n**********(" + time.asctime(time.localtime(time.time())) + ") Define NN structure End **********")

print("\n**********(" + time.asctime(time.localtime(time.time())) + ") Train and Test NN Begin: **********")
# run
config = tf.ConfigProto()
config.gpu_options.allow_growth = True

fold = 10
for curr_fold in range(fold):
    fold_size = cnn_datasets.shape[0]//fold
    indexes_list = [i for i in range(len(cnn_datasets))]
    indexes = np.array(indexes_list)
    split_list = [i for i in range(curr_fold*fold_size,(curr_fold+1)*fold_size)]
    split = np.array(split_list)
    cnn_test_x = cnn_datasets[split] 
    test_y = labels[split]

    split = np.array(list(set(indexes_list)^set(split_list)))
    cnn_train_x = cnn_datasets[split] 
    train_y = labels[split]

    train_sample = len(train_y)
    test_sample = len(test_y)
    print("training examples:", train_sample)
    print("test examples    :",test_sample)
    # set train batch number per epoch
    batch_num_per_epoch = math.floor(cnn_train_x.shape[0]/batch_size)+ 1

    # set test batch number per epoch
    accuracy_batch_size = batch_size
    train_accuracy_batch_num = batch_num_per_epoch
    test_accuracy_batch_num = math.floor(cnn_test_x.shape[0]/batch_size)+ 1

    # print label
    one_hot_labels = np.array(list(pd.get_dummies(lables_backup)))
    print(one_hot_labels)

    with tf.Session(config=config) as session:
        session.run(tf.global_variables_initializer())
        train_accuracy_save = np.zeros(shape=[0], dtype=float)
        test_accuracy_save = np.zeros(shape=[0], dtype=float)
        test_loss_save = np.zeros(shape=[0], dtype=float)
        train_loss_save = np.zeros(shape=[0], dtype=float)
        for epoch in range(training_epochs):
            print("learning rate: ",learning_rate)
            cost_history = np.zeros(shape=[0], dtype=float)
            for b in range(batch_num_per_epoch):
                start = b* batch_size
                if (b+1)*batch_size>train_y.shape[0]:
                    offset = train_y.shape[0] % batch_size
                else:
                    offset = batch_size
                #offset = (b * batch_size) % (train_y.shape[0] - batch_size)
                #print("start->end:",start,"->",start+offset)
                cnn_batch = cnn_train_x[start:(start + offset), :, :, :, :]
                cnn_batch = cnn_batch.reshape(len(cnn_batch) * window_size, 9, 9, 1)
                # print("cnn_batch shape:",cnn_batch.shape)
                batch_y = train_y[start:(offset + start), :]
                _, c = session.run([optimizer, cost],
                                   feed_dict={cnn_in: cnn_batch, Y: batch_y, keep_prob: 1 - dropout_prob,
                                              phase_train: True})
                cost_history = np.append(cost_history, c)
            if (epoch % 1 == 0):
                train_accuracy = np.zeros(shape=[0], dtype=float)
                test_accuracy = np.zeros(shape=[0], dtype=float)
                test_loss = np.zeros(shape=[0], dtype=float)
                train_loss = np.zeros(shape=[0], dtype=float)

                for i in range(train_accuracy_batch_num):
                    start = i* batch_size
                    if (i+1)*batch_size>train_y.shape[0]:
                        offset = train_y.shape[0] % batch_size
                    else:
                        offset = batch_size
                    #offset = (i * accuracy_batch_size) % (train_y.shape[0] - accuracy_batch_size)
                    train_cnn_batch = cnn_train_x[start:(start + offset), :, :, :, :]
                    train_cnn_batch = train_cnn_batch.reshape(len(train_cnn_batch) * window_size, 9, 9, 1)
                    train_batch_y = train_y[start:(start + offset), :]

                    train_a, train_c = session.run([accuracy, cost],
                                                   feed_dict={cnn_in: train_cnn_batch,Y: train_batch_y, keep_prob: 1.0, phase_train: False})

                    train_loss = np.append(train_loss, train_c)
                    train_accuracy = np.append(train_accuracy, train_a)
                print("(" + time.asctime(time.localtime(time.time())) + ") Epoch: ", epoch + 1, " Training Cost: ",
                      np.mean(train_loss), "Training Accuracy: ", np.mean(train_accuracy))
                train_accuracy_save = np.append(train_accuracy_save, np.mean(train_accuracy))
                train_loss_save = np.append(train_loss_save, np.mean(train_loss))

                for j in range(test_accuracy_batch_num):
                    start = j * batch_size
                    if (j+1)*batch_size>test_y.shape[0]:
                        offset = test_y.shape[0] % batch_size
                    else:
                        offset = batch_size
                    #offset = (j * accuracy_batch_size) % (test_y.shape[0] - accuracy_batch_size)
                    test_cnn_batch = cnn_test_x[start:(offset + start), :, :, :, :]
                    test_cnn_batch = test_cnn_batch.reshape(len(test_cnn_batch) * window_size, 9, 9, 1)
                    test_batch_y = test_y[start:(offset + start), :]

                    test_a, test_c = session.run([accuracy, cost],
                                                 feed_dict={cnn_in: test_cnn_batch,Y: test_batch_y,keep_prob: 1.0, phase_train: False})

                    test_accuracy = np.append(test_accuracy, test_a)
                    test_loss = np.append(test_loss, test_c)

                print("(" + time.asctime(time.localtime(time.time())) + ") Epoch: ", epoch + 1, " Test Cost: ",
                      np.mean(test_loss), "Test Accuracy: ", np.mean(test_accuracy), "\n")
                test_accuracy_save = np.append(test_accuracy_save, np.mean(test_accuracy))
                test_loss_save = np.append(test_loss_save, np.mean(test_loss))

            # reshuffle
            index_2 = np.array(range(0, len(train_y)))
            np.random.shuffle(index_2)
            cnn_train_x=cnn_train_x[index_2]
            train_y=train_y[index_2]

            # learning_rate decay
            if(np.mean(train_accuracy)<0.9):
                learning_rate=1e-4
            elif(0.9<np.mean(train_accuracy)<0.95):
                learning_rate=5e-5
            elif(0.99<np.mean(train_accuracy)):
                learning_rate=5e-6

        test_accuracy = np.zeros(shape=[0], dtype=float)
        test_loss = np.zeros(shape=[0], dtype=float)
        test_pred = np.zeros(shape=[0], dtype=float)
        test_true = np.zeros(shape=[0, 2], dtype=float)
        test_posi = np.zeros(shape=[0, 2], dtype=float)
        for k in range(test_accuracy_batch_num):
            start = k * batch_size
            if (k+1)*batch_size>test_y.shape[0]:
                offset = test_y.shape[0] % batch_size
            else:
                offset = batch_size
            #offset = (k * accuracy_batch_size) % (test_y.shape[0] - accuracy_batch_size)
            test_cnn_batch = cnn_test_x[start:(offset + start), :, :, :, :]
            test_cnn_batch = test_cnn_batch.reshape(len(test_cnn_batch) * window_size, 9, 9, 1)
            test_batch_y = test_y[start:(offset + start), :]

            test_a, test_c, test_p, test_r = session.run([accuracy, cost, y_pred, y_posi],
                                                         feed_dict={cnn_in: test_cnn_batch,Y: test_batch_y, keep_prob: 1.0, phase_train: False})
            test_t = test_batch_y

            test_accuracy = np.append(test_accuracy, test_a)
            test_loss = np.append(test_loss, test_c)
            test_pred = np.append(test_pred, test_p)
            test_true = np.vstack([test_true, test_t])
            test_posi = np.vstack([test_posi, test_r])
        # test_true = tf.argmax(test_true, 1)
        test_pred_1_hot = np.asarray(pd.get_dummies(test_pred), dtype=np.int8)
        test_true_list = tf.argmax(test_true, 1).eval()

        # recall
        test_recall = recall_score(test_true, test_pred_1_hot, average=None)
        # precision
        test_precision = precision_score(test_true, test_pred_1_hot, average=None)
        # f1 score
        test_f1 = f1_score(test_true, test_pred_1_hot, average=None)
        # auc
        # test_auc = roc_auc_score(test_true, test_pred_1_hot, average=None)
        # confusion matrix
        # confusion_matrix = confusion_matrix(test_true_list, test_pred)
        print("********************recall:", test_recall)
        print("*****************precision:", test_precision)
        # print("******************test_auc:", test_auc)
        print("******************f1_score:", test_f1)
        # print("**********confusion_matrix:\n", confusion_matrix)

        print("(" + time.asctime(time.localtime(time.time())) + ") Final Test Cost: ", np.mean(test_loss),
              "Final Test Accuracy: ", np.mean(test_accuracy))
        # save result
    #    os.system("mkdir -p ./result/cnn_rnn_parallel/tune_rnn_layer/" + output_dir)
        result = pd.DataFrame(
            {'epoch': range(1, epoch + 2), "train_accuracy": train_accuracy_save, "test_accuracy": test_accuracy_save,
             "train_loss": train_loss_save, "test_loss": test_loss_save})

        ins = pd.DataFrame({'conv_1': conv_1_shape, 'conv_2': conv_2_shape,'conv_3': conv_3_shape,
                            'cnn_fc': fc_size,'accuracy': np.mean(test_accuracy),
                            'keep_prob': 1 - dropout_prob,"calibration": calibration,
                            'sliding_window': window_size, "epoch": epoch + 1, "norm": norm_type,
                            "learning_rate": learning_rate, "regularization": regularization_method,
                            "train_sample": train_sample, "test_sample": test_sample,"batch_size":batch_size}, index=[0])
    #    summary = pd.DataFrame({'class': one_hot_labels, 'recall': test_recall, 'precision': test_precision,
    #                            'f1_score': test_f1})  # , 'roc_auc':test_auc})
        writer = pd.ExcelWriter(
            "./result/2-3D-CNN/"+arousal_or_valence+"/"+ data_file+"_"+str(curr_fold)+ ".xlsx")
        ins.to_excel(writer, 'condition', index=False)
        result.to_excel(writer, 'result', index=False)
    #    summary.to_excel(writer, 'summary', index=False)
        # fpr, tpr, auc
        fpr = dict()
        tpr = dict()
        roc_auc = dict()
        i = 0
        for key in one_hot_labels:
            fpr[key], tpr[key], _ = roc_curve(test_true[:, i], test_posi[:, i])
            roc_auc[key] = auc(fpr[key], tpr[key])
            roc = pd.DataFrame({"fpr": fpr[key], "tpr": tpr[key], "roc_auc": roc_auc[key]})
            roc.to_excel(writer, str(key), index=False)
            i += 1
        writer.save()
        '''
        with open("./result/cnn_rnn_parallel/tune_rnn_layer/"+output_dir+"/confusion_matrix.pkl", "wb") as fp:
            pickle.dump(confusion_matrix, fp)
        '''
        # save model
        model_dict= {}
        for variable in tf.trainable_variables():
            print(variable.name,"-->",variable.get_shape())
            model_dict[variable.name]=session.run(variable)
        sio.savemat(arousal_or_valence+"_"+data_file+"2D_3D_model.mat",model_dict)
        '''
        saver = tf.train.Saver()
        saver.save(session,
                   "./result/cnn_rnn_parallel/tune_rnn_layer/" + output_dir + "/model_" + output_file)
        '''
        print("**********(" + time.asctime(time.localtime(time.time())) + ") Train and Test NN End **********\n")
