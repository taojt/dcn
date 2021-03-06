#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time:  2018/9/18 16:16
# @Author:  jessetjiang

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import tensorflow as tf
from time import time
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.metrics import roc_auc_score


class DCN(BaseEstimator, TransformerMixin):
    def __init__(self, cate_feature_size, field_size, numeric_feature_size,
                 embedding_size=8, deep_layers=[32, 32],
                 dropout_deep=[0.5, 0.5, 0.5],
                 deep_layers_activation=tf.nn.relu,
                 epoch=10, batch_size=512,
                 learning_rate=0.001, optimizer_type="adam",
                 batch_norm=0, batch_norm_decay=0.995,
                 verbose=False, random_seed=2018,
                 loss_type="logloss", eval_metric=roc_auc_score,
                 l2_reg=0, greater_is_better=True, cross_layer_num=3):
        assert loss_type in ["logloss", "mse"], \
            "loss_type can be either 'logloss' for classification task or 'mse' for regression task"

        self.cate_feature_size = cate_feature_size
        self.numeric_feature_size = numeric_feature_size
        self.field_size = field_size
        self.embedding_size = embedding_size
        self.total_size = self.field_size * self.embedding_size + self.numeric_feature_size
        self.deep_layers = deep_layers
        self.cross_layer_num = cross_layer_num
        self.dropout_deep = dropout_deep
        self.deep_layers_activation = deep_layers_activation
        self.l2_reg = l2_reg

        self.epoch = epoch
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.optimizer_type = optimizer_type

        self.batch_norm = batch_norm
        self.batch_norm_decay = batch_norm_decay

        self.verbose = verbose
        self.random_seed = random_seed
        self.loss_type = loss_type
        self.eval_metric = eval_metric
        self.greater_is_better = greater_is_better

        self.train_result, self.valid_result = [], []

        self._init_graph()

    # 初始化计算图(TensorFlow的计算模型是基于计算图实现的)
    def _init_graph(self):
        self.graph = tf.Graph()

        with self.graph.as_default():
            tf.set_random_seed(self.random_seed)
            """
                       1、tf.Variable：主要在于一些可训练变量（trainable variables），比如模型的权重（weights，W）或者偏执值（bias）;
                       2、tf.placeholder：用于得到传递进来的真实的训练样本：不必指定初始值，可在运行时，通过 Session.run 的函数的 feed_dict 参数指定；
                       TensorFlow 支持占位符placeholder。占位符并没有初始值，它只会分配必要的内存。在会话中，占位符可以使用 feed_dict 馈送数据。
                       feed_dict是一个字典，在字典中需要给出每一个用到的占位符的取值。
            """
            self.feat_index = tf.placeholder(tf.int32, shape=[None, None], name="feat_index")
            self.feat_value = tf.placeholder(tf.float32, shape=[None, None], name="feat_value")

            self.numeric_value = tf.placeholder(tf.float32, shape=[None, None], name="numeric_value")

            self.label = tf.placeholder(tf.float32, shape=[None, 1], name="label")
            self.dropout_keep_deep = tf.placeholder(tf.float32, shape=[None], name="dropout_keep_deep")
            self.train_phase = tf.placeholder(tf.bool, name="train_phase")

            self.weights = self._initialize_weights()

            # data preprossing
            self.embeddings = tf.nn.embedding_lookup(self.weights['feature_embeddings'], self.feat_index)  # N*F*K

            feat_value = tf.reshape(self.feat_value, shape=[-1, self.field_size, 1])
            self.embeddings = tf.multiply(self.embeddings, feat_value)

            self.x0 = tf.concat(
                [self.numeric_value, tf.reshape(self.embeddings, shape=[-1, self.field_size * self.embedding_size])],
                axis=1)

            # deep part
            """ 
            learning_trick:神经网络的计算，是基于矩阵运算的，矩阵的维度等于神经元的个数。
            """
            """
            输出的非0元素是原来的 “1/keep_prob” 倍, keep_prob=self.dropout_keep_deep[0]
            """
            self.y_deep = tf.nn.dropout(self.x0, self.dropout_keep_deep[0])

            for i in range(0, len(self.deep_layers)):
                # dnn layser
                self.y_deep = tf.add(tf.matmul(self.y_deep, self.weights["deep_layer_%d" % i]),
                                     self.weights["deep_bias_%d" % i])
                self.y_deep = self.deep_layers_activation(self.y_deep)
                self.y_deep = tf.nn.dropout(self.y_deep, self.dropout_keep_deep[i+1])

            # cross part
            self._x0 = tf.reshape(self.x0, (-1, self.total_size, 1))
            x_l = self._x0
            for l in range(self.cross_layer_num):
                x_l = tf.tensordot(tf.matmul(self._x0, x_l, transpose_b=True), self.weights["cross_layer_%d" % l], 1) + \
                      self.weights["cross_layer_%d" % l] + x_l


            self.cross_network_out = tf.reshape(x_l, (-1, self.total_size))

            # concat part, join train
            concat_input = tf.concat([self.cross_network_out, self.y_deep], axis=1)
            self.out = tf.add(tf.matmul(concat_input, self.weights["concate_projection"]), self.weights["concate_bias"])

            # loss
            if self.loss_type == "logloss":
                self.out = tf.nn.sigmoid(self.out)
                self.loss = tf.losses.log_loss(self.label, self.out)
            elif self.loss_type == "mse":
                self.loss = tf.nn.l2_loss(tf.subtract(self.label, self.out))

            # l2 regularization on weights
            if self.l2_reg > 0:
                self.loss += tf.contrib.layers.l2_regularizer(
                    self.l2_reg)(self.weights["concate_projection"])
                for i in range(len(self.deep_layers)):
                    self.loss += tf.contrib.layers.l2_regularizer(self.l2_reg)(self.weights["deep_layer_%d" % i])

                for i in range(self.cross_layer_num):
                    self.loss += tf.contrib.layers.l2_regularizer(self.l2_reg)(self.weights["cross_layer_%d" % i])

                # Choose optimizer and use it to train model xx.minize(loss)
                if self.optimizer_type == "adam":
                    self.optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate, beta1=0.9, beta2=0.999,
                                                            epsilon=1e-8).minimize(self.loss)
                elif self.optimizer_type == "adagrad":
                    self.optimizer = tf.train.AdagradOptimizer(learning_rate=self.learning_rate,
                                                               initial_accumulator_value=1e-8).minimize(self.loss)
                elif self.optimizer_type == "gd":
                    self.optimizer += tf.train.GradientDescentOptimizer(learning_rate=self.learning_rate).minimize(
                        self.loss)
                elif self.optimizer_type == "momentum":
                    self.optimizer += tf.train.MomentumOptimizer(learning_rate=self.learning_rate,
                                                                 momentum=0.95).minimize(self.loss)

                # init
                self.saver = tf.train.Saver()
                init = tf.global_variables_initializer()
                self.sess = tf.Session()
                self.sess.run(init)

                # number of params
                total_parameters = 0
                for variable in self.weights.values():
                    shape = variable.get_shape()
                    variable_parameters = 1
                    for dim in shape:
                        variable_parameters *= dim.value
                    total_parameters += variable_parameters

                if self.verbose > 0:
                    print("#params: %d" % total_parameters)

    def _initialize_weights(self):
        weights = dict()

        # embeddings
        weights["feature_embeddings"] = tf.Variable(
            tf.random_normal([self.cate_feature_size, self.embedding_size], 0.0, 0.01), name="feature_embeddings")
        weights["feature_bias"] = tf.Variable(tf.random_normal([self.cate_feature_size, 1], 0.0, 1.0),
                                              name="feature_bias")

        # deep layer
        num_layer = len(self.deep_layers)
        glorot = np.sqrt(2.0 / (self.total_size + self.deep_layers[0]))

        """ 
        1、如果权重初始为0， 由于网络中的神经元的更新机制完全相同，由于网络的对称性，会产生各个layer中产生相同的梯度更新，导致所有的权重最后值相同，收敛会出现问题。
        2、scale:标准差
        3、deep部分的第一层是input_layer，所以权重的长度是total_size，但一共仍然只有deep_layers[0]个神经元来接收这些input_data。
        """
        weights["deep_layer_0"] = tf.Variable(
            np.random.normal(loc=0, scale=glorot, size=(self.total_size, self.deep_layers[0])), dtype=np.float32)
        weights["deep_bias_0"] = tf.Variable(np.random.normal(loc=0, scale=glorot, size=(1, self.deep_layers[0])),
                                             dtype=np.float32)

        for i in range(1, num_layer):
            # 权重初始化的trick：权重应该是满足均值为0，方差为2除以两层神经元个数之和
            glorot = np.sqrt(2.0 / (self.deep_layers[i - 1] + self.deep_layers[i]))
            weights["deep_layer_%d" % i] = tf.Variable(
                np.random.normal(loc=0, scale=glorot, size=(self.deep_layers[i - 1], self.deep_layers[i])),
                dtype=np.float32)
            weights["deep_bias_%d" % i] = tf.Variable(
                np.random.normal(loc=0, scale=glorot, size=(1, self.deep_layers[i])), dtype=np.float32)

        for i in range(self.cross_layer_num):
            weights["cross_layer_%d" % i] = tf.Variable(
                np.random.normal(loc=0, scale=glorot, size=(self.total_size, 1)), dtype=np.float32)
            weights["cross_bias_%d" % i] = tf.Variable(np.random.normal(loc=0, scale=glorot, size=(self.total_size, 1)),
                                                       dtype=np.float32)

        # final concate projection layer
        input_size = self.total_size + self.deep_layers[-1]
        glorot = np.sqrt(2.0 / (input_size + 1))

        weights["concate_projection"] = tf.Variable(np.random.normal(loc=0, scale=glorot, size=(input_size, 1)),
                                                    dtype=np.float32)
        weights["concate_bias"] = tf.Variable(tf.constant(0.01), dtype=np.float32)

        return weights

    # 获取训练batch
    def get_batch(self, Xi, Xv, Xv2, y, batch_size, index):
        start = index * batch_size
        end = (index + 1) * batch_size
        end = end if end < len(y) else len(y)  # 最后一个batch

        return Xi[start:end], Xv[start:end], Xv2[start:end], [[y_] for y_ in y[start:end]]

    # shuffle the list
    def shuffle_in_unison_scary(self, a, b, c, d):
        rng_state = np.random.get_state()
        np.random.shuffle(a)
        np.random.set_state(rng_state)
        np.random.shuffle(b)
        np.random.set_state(rng_state)
        np.random.shuffle(c)
        np.random.set_state(rng_state)
        np.random.shuffle(d)

    # predict
    def predict(self, Xi, Xv, Xv2, y):
        """
        :param Xi: list of list of feature indices of each sample in the dataset
        :param Xv: list of list of feature values of each sample in the dataset
        :return: predicted probability of each sample
        """
        feed_dict = {self.feat_index: Xi,
                     self.feat_value: Xv,
                     self.numeric_value: Xv2,
                     self.label: y,
                     self.dropout_keep_deep: [1.0] * len(self.dropout_deep),
                     self.train_phase: True
                     }
        loss = self.sess.run([self.loss], feed_dict=feed_dict)

        return loss

    # train model by session.run()
    def fit_on_batch(self, Xi, Xv, Xv2, y):
        feed_dict = {self.feat_index: Xi,
                     self.feat_value: Xv,
                     self.numeric_value: Xv2,
                     self.label: y,
                     self.dropout_keep_deep: self.dropout_deep,
                     self.train_phase: True
                     }

        loss, opt = self.sess.run([self.loss, self.optimizer], feed_dict=feed_dict)

        return loss

    # train model by calling fit_on_batch() function
    def fit(self, cate_Xi_train, cate_Xv_train, numeric_Xv_train, y_train, cate_Xi_valid=None, cate_Xv_valid=None,
            numeric_Xv_valid=None, y_valid=None, early_stopping=False, refit=False):
        print(len(cate_Xi_train))
        print(len(cate_Xv_train))
        print(len(numeric_Xv_train))
        print(len(y_train))

        has_valid = cate_Xv_valid is not None

        for epoch in range(self.epoch):
            t1 = time()
            self.shuffle_in_unison_scary(cate_Xi_train, cate_Xv_train, numeric_Xv_train, y_train)
            total_batch = int(len(y_train) / self.batch_size)
            for i in range(total_batch):
                cate_Xi_batch, cate_Xv_batch, numeric_Xv_batch, y_batch = self.get_batch(cate_Xi_train, cate_Xv_train,
                                                                                         numeric_Xv_train, y_train,
                                                                                         self.batch_size, i)

                self.fit_on_batch(cate_Xi_batch, cate_Xv_batch, numeric_Xv_batch, y_batch)

                # 计算loss
                if has_valid:
                    y_valid = np.array(y_valid).reshape(-1, 1)
                    loss = self.predict(cate_Xi_valid, cate_Xv_valid, numeric_Xv_valid, y_valid)
                    print("epoch: {0}, loss: {1}.".format(epoch, loss))

        # free
        self.sess.close()
