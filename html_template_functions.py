#########################################################################################################
# Notes
# 1. "Sky High" bug. Fixed
# 2. Search multiple words movie. 
# 3. Resolve output of movies with same name. Ex Sky High 2005 vs Sky High 2003. Fixed
#########################################################################################################

import numpy as np
import pandas as pd
import re
pd.set_option('display.max_columns', None)
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn import metrics
from scipy.sparse import csr_matrix
import sys
import os
import click
import sys

# Import Dataset
def load_content_rec_data():
    #dir_path = os.path.dirname(os.path.realpath(__file__))
    # Import movie dataset (combined metadata), subset the data to 10k rows for computational conviencies
    whole_df = pd.read_csv('static/combined_metadata_table.csv')
    return whole_df


# Pick A Movie (Fake Search Engine)
def identify_movie(your_pick, whole_df):
    result = whole_df[whole_df['title'].str.contains(your_pick, flags=re.IGNORECASE, regex=True)]
    result = result.sort_values(by=['year'], ascending=False) # sort movies by recency
    return result


# Returns search result
def get_movies(your_pick_df):
    movie_list = []
    imdbid_list = []
    for i in range(len(your_pick_df)):
        cur_row = your_pick_df.iloc[i]
        movie = cur_row['title']
        year = cur_row['year']
        movie_output = movie + ' ('+str(year)+')'
        imdb_id = cur_row['imdb_title_id']
        movie_list.append(movie_output)
        imdbid_list.append(imdb_id)
        #print(i,' :   ', movie, ' ('+str(year)+')')
        #html = html + str(i+1) + ' |   ' +  movie + ' ('+str(year)+')' + ' <br>     IMBD ID: ' + str(imdb_id) + "<br><br>"
    return imdbid_list, movie_list
        

# Subset Dataset by Genre
def subset_by_genre(your_pick, whole_df):
    genres = whole_df[whole_df['title'] == your_pick]['genre']
    genres = list(genres)[0].split(', ')
    masks = []
    for genre in genres:
        mask = whole_df['genre'].str.contains(genre, na=False)
        masks.append(mask)
    mask = masks[0]
    for i in range(1,len(masks)):
        mask = mask | masks[i]
        
    return whole_df[mask]


# Subset Dataset by Year
def subset_by_year(your_pick, whole_df, year_range=30):
    year = whole_df[whole_df['title'] == your_pick]['year']
    year = list(year)[0]
    window = [year-year_range, year+year_range]
    mask = (whole_df['year'] >= window[0]) & (whole_df['year'] <= window[1])
    
    return whole_df[mask]


# Subset Dataset by Language
def subset_by_language(your_pick, whole_df):
    languages = whole_df[whole_df['title'] == your_pick]['language']
    languages = list(languages)[0].split(', ')
    masks = []
    for language in languages:
        mask = whole_df['language'].str.contains(language, na=False)
        masks.append(mask)
    mask = masks[0]

    for i in range(1,len(masks)):
        mask = mask | masks[i]

    return whole_df[mask]



# Delete spaces in names to make names more unique
# eg. 'firstname lastname' -> 'firstnamelastname'
def delete_space_in_name_fields(source):
    column_with_names = ['director', 'writer', 'production_company', 'actors']
    source = source.copy()
    for col in column_with_names:
        source[str(col)] = source[str(col)].str.replace(' ', '', regex=True)
        source[str(col)] = source[str(col)].str.replace(',', ' ', regex=True)

    return source


def compute_tf_idf(source):
    columns = ['country', 'director','writer', 
               'production_company', 'actors',
               'description','overview', 'tagline']


    # Converts the source dataframe into single string for tfidf computation
    df = {}
    movies = []
    titles = []
    imdbid = []
    for i in range(source.shape[0]):
        row = source.iloc[i]
        row_str = ''
        titles.append(row['title'])
        imdbid.append(row['imdb_title_id'])
        for column in columns:
            row_str += str(row[column])
            row_str += ' '
        movies.append(row_str)

    df['IMDBid'] = imdbid
    df['Title'] = titles
    df['Content'] = movies
    df = pd.DataFrame(df)
    df.head()

    V = TfidfVectorizer()
    X = V.fit_transform(df['Content'])
    return X, df




def cos_similarity(X, df, your_pick):
    # Compute similarity of movie: Melvin and Howard
    index = df[df['Title'] == your_pick].index[0]
    d1 = list(csr_matrix.toarray(X[index]))
    mag_d1 = np.linalg.norm(d1)
    dist = []
    for i in range(X.shape[0]):
        row = list(csr_matrix.toarray(X[i]))
        dot_product_xy = np.multiply(d1, row).sum(1)
        mag_row = np.linalg.norm(row)
        x_time_y = mag_d1 * mag_row
        dist.append(dot_product_xy/x_time_y) 
    dist_series = pd.Series(dist)
    dist_series = dist_series.sort_values(ascending=False)
    dist_series = dist_series.iloc[1:6]
    dist_series = pd.DataFrame(dist_series)
    
    return dist_series


# Recommend Top 5 Movies
def recommend_movies(df, dist_series):
    # Merge similarity scores with original dataframe to visualize
    result = pd.merge(dist_series, df, how='inner', left_index=True, right_index=True)
    result = result.rename({0: 'Cosine Similarity Score'}, axis='columns')
    return result


def format_output_to_console(result, num_recommendations=6):
    return list(result.iloc[:num_recommendations]['IMDBid']), list(result.iloc[:num_recommendations]['Title'])
    
def return_search_results(your_pick):
    whole_df = load_content_rec_data()
    your_pick_df = identify_movie(your_pick, whole_df) 
    if len(your_pick_df) == 0:
        return -1, [], []
    imdbid_list, movie_list = get_movies(your_pick_df)
    #print('SHOW:', movie_list)
    return 0, imdbid_list, movie_list
    
def get_recommendations(imdb_id):
    whole_df = load_content_rec_data()
    your_pick = str(list(whole_df[whole_df['imdb_title_id'] == imdb_id]['title'])[0])
    source = subset_by_genre(your_pick, whole_df)
    source = subset_by_year(your_pick, source)
    source = subset_by_language(your_pick, source)
    source = delete_space_in_name_fields(source)
    X, df = compute_tf_idf(source)
    dist_series = cos_similarity(X, df, your_pick)
    result = recommend_movies(df, dist_series)
    return format_output_to_console(result)


if __name__ == "__main__":  
    
    if len(sys.argv) < 2:
        raise Exception('Please enter 1 movie title! You have entered {} titles :('.format(len(sys.argv[1:])))
    
    your_pick = ' '.join(sys.argv[1:])
    whole_df = load_content_rec_data()
    your_pick_df = identify_movie(your_pick, whole_df)  
    
    if len(your_pick_df) == 0:
        raise Exception('\nNo movies exist with the movie keyword you specified. \nPlease try again with a different movie.\n')
    
    is_valid_index, val = get_one_move(your_pick_df)
        
    if is_valid_index is not True:
        raise Exception('You have not picked a valid movie index! You have entered {} :('.format(val))
    
    your_pick = str(your_pick_df.iloc[val]['title'])
    
    
    source = subset_by_genre(your_pick, whole_df)
    source = subset_by_year(your_pick, source)
    source = subset_by_language(your_pick, source)
    source = delete_space_in_name_fields(source)
    X, df = compute_tf_idf(source)
    dist_series = cos_similarity(X, df, your_pick)
    result = recommend_movies(df, dist_series)
    format_output_to_console(result)

