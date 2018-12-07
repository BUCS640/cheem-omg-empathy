import sys
from gensim.models import KeyedVectors
import torch
import os
import time

sys.path.append("/raid/omgempathy/")  # path to the main dir
from src.textbased_model import utils, config
from src.sample import calculateCCC
from src.textbased_model.models import LSTM_with_Attention
from src.textbased_model.datasets import Utterances_Chunk_Eval
import argparse
from nltk.corpus import stopwords
import numpy as np


en_stopwords = None
if not config.use_stopwords:
    en_stopwords = set(stopwords.words('english'))

parser = argparse.ArgumentParser("Run trained model on train/val (validation)")
parser.add_argument("-m", "--model", help="model's id, e.g., model_1542296294_999", required=True)
parser.add_argument('-s', '--source', help="data source: train/val", default="val")
parser.add_argument('-d', '--difference', help="trained on different?: 0: No (actuall value), 1: Yes", default=1, type=int)

args = vars(parser.parse_args())
trained_on_difference = (args['difference'] == 1)
model_name = args['model']
model_file = 'data/Training/models/{}.pt'.format(model_name)
model_id = model_name[model_name.index("_") + 1:]
model_timestamp = model_id[:model_id.index("_")]

# print(model_id)
data_source_name = "Validation"
data_source = config.validation

if args['source'] == "train":
    data_source = config.training
    data_source_name = "Training"

if torch.cuda.is_available():
    torch.cuda.set_device(1)
    print("#GPUs: {}".format(torch.cuda.device_count()))
    print("Current GPU: {}".format(torch.cuda.current_device()))

# from importlib import reload
device = config.device

# load config
config_file = 'data/Training/training_logs/{}.config'.format(model_timestamp)
configs = utils.load_model_config(config_file)
keywords = config.config_keywords
input_dim = config.input_dim
lstm_dim = config.lstm_dim
ln1_dim = config.ln1_output_dim
dropout = 0  # no drop out
chunk_size = 10
chunk_step = -1

if keywords['lstm_dim'] in configs:
    lstm_dim = int(configs[keywords['lstm_dim']])

if keywords['ln1_output_dim'] in configs:
    ln1_dim = int(configs[keywords['ln1_output_dim']])

if "chunk_size" in configs:
    chunk_size = int(configs["chunk_size"])

print("lstm_dim: {}\tln1_dim: {}\tdropout: {}".format(lstm_dim, ln1_dim, dropout))

model_pred_output = data_source['prediction_output']
utils.mkdir(model_pred_output)
model_pred_output = os.path.join(model_pred_output, "{}_utter_chunk_attention".format(model_id))
utils.mkdir(model_pred_output)

print("Loading validation data...")
start = time.time()
data = utils.load_data_dir(data_source['data'])  # {filename: OrderDict {utter_id: (text, score, startframe, endframe)}}

print("Loading groundtruth sequences...")
gt_sequences = utils.load_groundtruth_sequences(data_source['labels'])

# word_embeddings_file = config.glove_word2vec_file
word_embeddings_file = config.glove_word2vec_file_filtered
print("Loading word embeddings...")
we_model = KeyedVectors.load_word2vec_format(word_embeddings_file, binary=False)
vocabs = we_model.wv.vocab

model = LSTM_with_Attention(input_dim, lstm_dim, ln1_dim, attn_len=chunk_size)
model.load_state_dict(torch.load(model_file))
model.to(device)

print("Compute avg word embeddings and convert to tensor")
data_tensor = utils.get_average_word_embeddings_for_utters(data, vocabs, we_model, en_stopwords)  # {fname: [list of utterances' embeddings (i.e., avg words' embeddings)]}
all_chunks = Utterances_Chunk_Eval(data_tensor, chunk_size, chunk_step=chunk_step)

start = time.time()

print("Run validation, results are saved to {}".format(model_pred_output))
model.eval()
for fname, chunks in all_chunks.chunks.items():
    predicted_scores = {}  # {index: [predicted scores] (later take average)}
    print("{}\t#chunks: {}".format(fname, len(chunks)))
    for chunk in chunks:
        X = chunk[0].to(device)
        X = X.view(X.shape[0], 1, -1)  # (chunk_len, batch, input_dim)
        # print(X)
        valid_indices = chunk[2]
        with torch.no_grad():
            pred = model(X)
        pred = pred.view(-1, 1)
        # print(pred)
        # print("----")
        # add predicted values to scores list (for each valid frames)
        for tmp_index, predicted in enumerate(pred):
            real_index = valid_indices[tmp_index]
            if real_index not in predicted_scores:
                predicted_scores[real_index] = [predicted]
            else:
                predicted_scores[real_index].append(predicted)

    # after predicting for all the chunks, generate the sequence

    predicted_sequence = []  # store the predicted sequence
    prev_predicted = 0.0  # in case the "utterance" tensor is None --> use the previous score (to keep continuity)
    tmp_info = data[fname]

    indices = data[fname].keys()
    for utter_index in indices:
        tmp = tmp_info[utter_index]
        start_index = tmp[2]  # start frame
        end_index = tmp[3]  # end frame
        if utter_index not in predicted_scores:
            utils.add_value_to_sequence(prev_predicted, predicted_sequence, start_index, end_index)
            continue
        new_value = np.average(predicted_scores[utter_index])
        if trained_on_difference:
            prev_predicted = prev_predicted + new_value
        else:
            prev_predicted = new_value
        utils.add_value_to_sequence(prev_predicted, predicted_sequence, start_index, end_index)

    # after finish for 1 file, stores the predicted sequence
    gt_sequence = gt_sequences[fname]
    predicted_sequence = utils.refine_predicted_sequence(predicted_sequence, len(gt_sequence))
    # write result
    pred_output_file = os.path.join(model_pred_output, "{}.csv".format(fname))
    utils.write_predicted_sequences(predicted_sequence, pred_output_file)


# after finishing the running, run the evaluation
gt_dir = "data/{}/Annotations".format(data_source_name)
# print("GT: {}".format(gt_dir))
# print("pred: {}".format(model_pred_output))
calculateCCC.calculateCCC(gt_dir, model_pred_output)




