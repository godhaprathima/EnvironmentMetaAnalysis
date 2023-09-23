# EnviroMetaAnalysis

#### Mark Green

This notebook runs a network analysis to produce summary visualizations based on journal article metadata collected from `OpenAlex`. Running the `Alex2Mongo` pipeline is a prerequite to query the OpenAlex API for article metadata of articles within the selected *journals of interest*. The `Alex2Mongo` pipeline writes these metadata as documents to a `mongodb` database served in a `Docker` container on port 27017. The Docker image is also available on [Docker Hub](https://hub.docker.com/repository/docker/greenmmq/envirometaanalysis/general). However, the `data/db` volume is not and must still be compiled with `Alex2Mongo.py` to create a database of a size approximately ~3.3 Gb. Alternatively, contact the repository Admin for a copy of that database. 

# Initialize Analysis

This notebook connects to the created `mongodb` database to garner insight into the global distribution of research efforts for various topics related to environmental science (as curated by the *journals of interest*). To run the notebook, one must simply set the variables in the cell below, and execute all the cells. 

**User Variable Descriptions**
- `target_concept` should be a lower case string keyword - to filter for article's with a related topic as provided by the `concept` metadata object. 
- `n_samples` is an integer - determines how large a sample size to use for the analysis. Larger number = longer runtimes! It is unlikely you will be able to compute the full dataset on a regular laptop, so sampling is a necessity. However, by the *Law of Large Numbers*, this should serve the analysis just fine. 


```python
target_concept = 'environment'  # or 'all' for all of the samples...
n_samples = 10000
```

## Prepare Data

### GDP Data

The first step is to read-in GDP data and countries data. These economic data were gathered from the world bank and are read-in as excel spreadsheets. Because the GDP per capita (gdppc) varies across several orders of magnitude, the $\log(gdppc)$ is calculated for each country as well. This is used as a normalization term, so the $\log(gdppc)$ is a better choice for us later on. 


```python
import numpy as np
import pandas as pd

# read-in and clean income_level_data and gdp_per_capita

gdp_per_capita=pd.read_excel('../data/world bank GDP data.xls')
gdp_per_capita=gdp_per_capita.drop(columns={'Indicator Name', 'Country Name'})
gdp_per_capita=gdp_per_capita.rename(columns={'2022':'GDP per capita(US$)'})
gdp_per_capita=gdp_per_capita.drop_duplicates(subset=['Country Code'])

# gdp_per_capita

income_level_data=pd.read_excel('../data/world bank income division.xlsx')
income_level_data2=pd.read_excel('../data/world bank income2.xlsx')
income_level_data=income_level_data.drop(columns={'Income Group Code','Income Group'})
income_level_data=income_level_data.drop_duplicates()
income_level_data=income_level_data.merge(income_level_data2, right_on='Economy', left_on='Country')
income_level_data=income_level_data.drop(columns={'Economy'})

# income_level_data

country_stats = pd.merge(income_level_data, gdp_per_capita, left_on='Country Code', right_on='Country Code')
country_stats['log_gdppc'] = country_stats.apply(lambda row: np.log(row['GDP per capita(US$)']), axis=1)

print(country_stats)
```

        Country Code              Country         Income group  \
    0            ASM       American Samoa          High income   
    1            AND              Andorra          High income   
    2            ATG  Antigua and Barbuda          High income   
    3            ABW                Aruba          High income   
    4            AUS            Australia          High income   
    ..           ...                  ...                  ...   
    211          VUT              Vanuatu  Lower middle income   
    212          VNM              Vietnam  Lower middle income   
    213          PSE   West Bank and Gaza  Upper middle income   
    214          ZMB               Zambia  Lower middle income   
    215          ZWE             Zimbabwe  Lower middle income   
    
         GDP per capita(US$)  log_gdppc  
    0           15743.310758   9.664171  
    1           41992.793358  10.645253  
    2           18745.173509   9.838692  
    3           29342.100730  10.286779  
    4           64491.429886  11.074288  
    ..                   ...        ...  
    211          3010.292173   8.009792  
    212          4163.514300   8.334115  
    213          3789.327966   8.239944  
    214          1487.907764   7.305126  
    215          1266.996031   7.144404  
    
    [216 rows x 5 columns]


### Connect to `mongodb`

The next step is to read-in the data from the `mongodb`. Remember! It is a prerequisite to have successfully executed the `Alex2Mongo.py` pipeline and created a `mongodb` database server in a `docker` container running on port `27017`. You may also have to update the database client and collection names depending on how `Alex2Mongo.py` is parameterized. 


```python
%%time

# first connect to the docker container with all the right fields
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

uri = "mongodb://localhost:27017/?retryWrites=true&w=majority"
client = MongoClient(uri, server_api=ServerApi('1'))
database = client["test_db"]
collection = database["journals"]

print(f"Total number of Articles: {collection.count_documents({})}")

# collection.find_one()
```

    Total number of Articles: 1039248
    CPU times: user 204 ms, sys: 59.2 ms, total: 263 ms
    Wall time: 24.2 s


## Aggregate the data for network edges

### Concepts Pipeline

The `concepts_pipeline` gets a list of article ids for each concept from a random sampling of articles, set by the `n_samples`.


```python
%%time

import pandas as pd

# pipeline to get all concepts for all articles
concepts_pipeline = [
    {
        '$sample': { 'size': n_samples } 
    },
    {
        '$unwind': '$concepts'
    },
    {
        '$project': {
            '_id': 1,
            'type': 1,
            'concept': '$concepts.display_name'
        }
    },
    {
        '$match': {
            'type': 'article',
            'concept': {'$exists': True}
        }
    },
    {
        '$group': {
            '_id': '$concept',
            'article_ids': { '$addToSet': '$_id' }
        }
    },
    {
        '$project': {
            '_id': 1, 
            'article_ids': 1
        }
    }
]

# Execute the aggregation pipeline
concepts_result = collection.aggregate(concepts_pipeline)

# concepts_result.__dict__

concepts_results_list = []

# Iterate through the result and populate the list
for entry in concepts_result:
    try:
        concepts_results_list.append({
            'concept': entry['_id'],
            'article_ids': entry['article_ids']
        })
    except:
        continue

# Create a Pandas DataFrame from the results list
concepts_df = pd.DataFrame(concepts_results_list).sort_values(by='concept')
concepts_df['concept'] = concepts_df['concept'].str.lower()
concepts_df.set_index('concept', inplace=True)

# print(concepts_df)
print(len(set(concepts_df.index)))
```

    12051
    CPU times: user 221 ms, sys: 16.5 ms, total: 238 ms
    Wall time: 7.06 s


Run this next cell if you want to see a list of all the concepts. Warning! The output is long....


```python
# pprint(set(concepts_df.index))
```

The `concepts_df` results are filtered by the `target_concept` to select the ObjectIds only of the articles with concepts like the `target_concept`.


```python
%%time

import itertools
import pandas as pd 

unique_ids = list(set(itertools.chain.from_iterable(list(concepts_df['article_ids']))))
if target_concept=='all':
    id_list = list(set(itertools.chain.from_iterable(list(concepts_df['article_ids']))))
else:
    id_list = list(set(itertools.chain.from_iterable(list(concepts_df.filter(like=str(target_concept).lower(), axis=0)['article_ids']))))

print(f'unique articles sampled: {len(unique_ids)}')
print(f'articles like "{target_concept}": {len(id_list)}')
```

    unique articles sampled: 9930
    articles like "environment": 6182
    CPU times: user 77.9 ms, sys: 2.23 ms, total: 80.1 ms
    Wall time: 78.7 ms


At this stage, the `id_list` is a list of article IDs which have a concept like the `target_concept`. This is our sample set. 

### Article Pipeline

The `article_pipeline` gets the publication year for each article, and other citation metrics:

- `cited_by_count` is the total number of citations for the article
- `coauthor_count` is the number of coauthors on the article
- `cites_per_coauthor` is calculated as:

$$
\text{cites_per_coauthor} = 
\begin{cases}
    \text{coauthor_count} > 1 & \frac{\text{cited_by_count}}{{\text{coauthor_count}\choose{2}} \times 2} \\
    \text{coauthor_count} = 1 & \frac{\text{cited_by_count}}{2}
\end{cases}
$$

In this case, the number of citations for a given article is divided by the number of possible combinations of coauthor pairs. For articles with only 1 coauthor, it is divided by 2 instead. This prepares for weighting an edgelist for the network plots because for each article, *each pair of coauthors* forms an edge between the income level of the country of each coauthor. In this way, the total citations of a given article is distributed evenly across all the coauthor pairs such that the sum of the distributed `citations_per_coauthor` of each coauthor pair in the article will equal the total citations `cited_by_count` for the article. In the `author_pipeline`, single authors are duplicated; in this way, they are counted as a *self-loop* in the network instead of being dropped, thus the denominator for this special case must be 2. 


```python
%%time

import math
import pandas as pd

# pipeline to determine attributes for each article
article_pipeline = [
    {
        '$match': {
            '_id': {'$in': id_list},
            'type': 'article'
        }
    },
    {
        '$unwind': '$authorships'
    },
    {
        '$project': {
            '_id': 1,
            'type': 1,
            'publication_year': 1,
            'cited_by_count': 1,
            'country_code': {
                '$arrayElemAt': ['$authorships.institutions.country_code', 0]
            }
        }
    },
    {
        '$match': {
            'country_code': {'$exists': True}
        }
    },
    {
        '$group': {
            '_id': '$_id',
            'publication_year': {'$first':'$publication_year'},
            'cited_by_count': {'$first':'$cited_by_count'},
            'coauthor_count': {'$sum': 1}
        }
    },
    {
        '$project': {
            '_id': 1,
            'publication_year': 1,
            'cited_by_count': 1,
            'coauthor_count': 1
        }
    }
]

# Execute the aggregation pipeline
article_result = collection.aggregate(article_pipeline)

# article_result.__dict__

article_results_list = []

# Iterate through the result and populate the list
for entry in article_result:
    try:
        article_results_list.append({
            'pub_id': entry['_id'],
            'pub_year': entry['publication_year'],
            'cited_by_count': entry['cited_by_count'],
            'coauthor_count': entry['coauthor_count']
        })
    except:
        continue

# Create a Pandas DataFrame from the results list
article_df = pd.DataFrame(article_results_list)

article_df['cites_per_coauthor'] = article_df.apply(
    lambda row: row['cited_by_count']/(math.comb(row['coauthor_count'],2)*2) if math.comb(row['coauthor_count'],2)>0 else row['cited_by_count']/2, 
    axis=1
)
article_df.replace({'cites_per_coauthor': 0.}, 0.01, inplace=True)

# Display the DataFrame
print(article_df.sort_values('cites_per_coauthor'))

# article_result.__dict__
```

                            pub_id  pub_year  cited_by_count  coauthor_count  \
    3556  64d2fabdadb21da659ae88a2      2022               8              60   
    4491  64d307d5adb21da659b57810      2022               2              24   
    392   64d2fce1adb21da659af9d10      2022               1              16   
    2510  64d2f8aaadb21da659ad887a      2023               1              14   
    5847  64d2fa8eadb21da659ae71d7      2022               1              14   
    ...                        ...       ...             ...             ...   
    2659  64d302c5adb21da659b2a1b6      2013             692               3   
    4980  64d308a9adb21da659b5e47d      2013             259               2   
    3653  64d3095aadb21da659b63e14      2013             275               1   
    613   64d2f9d1adb21da659ae11e2      2017             322               1   
    2812  64d2ff0badb21da659b0cf98      2017             941               2   
    
          cites_per_coauthor  
    3556            0.002260  
    4491            0.003623  
    392             0.004167  
    2510            0.005495  
    5847            0.005495  
    ...                  ...  
    2659          115.333333  
    4980          129.500000  
    3653          137.500000  
    613           161.000000  
    2812          470.500000  
    
    [5939 rows x 5 columns]
    CPU times: user 198 ms, sys: 5.29 ms, total: 203 ms
    Wall time: 769 ms


While the `cited_by_count` is a good raw metric for the citations of an article, the `cites_per_coauthor` distributes the citations across the coauthors such that it can be used to weight the relationships between pairs of coauthors. One thing that is not done here is to have normalized the citations by the age of the article. Since the goal of this metric is to show the "power" of articles produced by relationships between authors from different income levels, this should be taken in consideration for future analysis runs. For example, an article with 60 citations in 2022 is probably a "more powerful" article than an article with 60 citations from 2012. 

### Author Pipeline

The `author_pipeline` gets the country code and position for all of the coauthors of each article. Articles with single authors are duplicated for network plotting as a *self-loop*. The result is a complete list of attributes for all the coauthors on all the queried articles.


```python
%%time

import pandas as pd
from iso3166 import countries

# this pipeline gets countries and positions of all authors

author_pipeline = [
    {
        '$match': {'_id': {'$in': id_list}}
    },
    {
        '$unwind': '$authorships'
    },
    {
        '$project': {
            '_id': 1,
            'type': 1,
            'country_code': {
                '$arrayElemAt': ['$authorships.institutions.country_code', 0]
            },
            'author_position': '$authorships.author_position'
        }
    },
    {
        '$match': {
            'type': 'article',
            'country_code': {'$exists': True}
        }
    }
]

# Execute the aggregation pipeline
author_result = collection.aggregate(author_pipeline)

# result.__dict__

# Create a list to store the results
author_results_list = []

# Iterate through the result and populate the list
for entry in author_result:
    try:
        author_results_list.append({
            'pub_id': entry['_id'],
            'country_code': countries.get(entry['country_code']).alpha3,
            'author_position': entry['author_position']
        })
    except:
        continue

# Create a Pandas DataFrame from the results list
author_df = pd.DataFrame(author_results_list)

# duplicate the single author rows - this gets the self-loops for the network plots
duplicated_pubs = author_df[author_df.duplicated(subset='pub_id', keep=False)]['pub_id']
singleauthor_rows = author_df[~author_df['pub_id'].isin(duplicated_pubs)]
author_df = pd.concat([author_df, singleauthor_rows], axis=0, ignore_index=True)

# Display the DataFrame
print(author_df)
```

                             pub_id country_code author_position
    0      64d2f6daadb21da659ac9f47          MYS           first
    1      64d2f6daadb21da659ac9f47          MYS          middle
    2      64d2f6daadb21da659ac9f47          MYS          middle
    3      64d2f6daadb21da659ac9f47          MYS          middle
    4      64d2f6daadb21da659ac9f47          MYS          middle
    ...                         ...          ...             ...
    31668  64d31416adb21da659bc247b          RUS           first
    31669  64d31417adb21da659bc2530          RUS           first
    31670  64d31417adb21da659bc2598          IDN           first
    31671  64d3142dadb21da659bc307d          IDN           first
    31672  64d314d4adb21da659bc7899          NGA           first
    
    [31673 rows x 3 columns]
    CPU times: user 164 ms, sys: 19.4 ms, total: 183 ms
    Wall time: 509 ms


### Compile Edgelists from Pipeline Results

This is the main computational bottleneck of the program. For ultimate flexibility, the results of the concepts and article pipelines are *left-joined* onto the author pipeline to create a massive edgelist dataframe. From this point, the `author_pairs` are reduced into simpler $3 \times n$ edgelist dataframes which can be read by the `nx.read_pandas_edgelist` method. 

Edglists are compiled in two formats: for grouping the nodes by *income group* or by *country code*. In the basic edgelist computation, the count of the coauthor pairs for each hierarchy is aggregated. Although the count aggregation of the coauthors is a more easily understood metric, it skews the results toward countries with large populations, IE greater resources to fund research - this relationship with GDP and population to increased article production are closely correlated as shown in the plots of article counts vs GDPPC. Thus, it is necessary to calculate a new metric to address this. 

Recall, the `cites_per_coauthor` metric is calculated for each article, and is now joined to each coauthor in each coauthor pair such that the sum of the `cites_per_coauthor` for all the coauthor pairs of a given article is equal to the total citations of the article. This addresses countries with large numbers of researchers by distributing the article weight (total citations) amongst all the coauthors. To account for the influence of GDPPC on the raw number of coauthors, the `cites_per_coauthor` is then normalized by the $\log(gdppc)$ of the country for each coauthor in the coauthor pair:

$$
\text{cites_norm_gdppc} = 
\begin{cases}
    \text{coauthor_count} > 1 & \frac{\text{cited_by_count}}{{\text{coauthor_count}\choose{2}} \times 2} / \log(gdppc) \\
    \text{coauthor_count} = 1 & \frac{\text{cited_by_count}}{2} / \log(gdppc)
\end{cases}
$$

With this new metric computed for each coauthor in the coauthor pair, it is then summed as `cites_norm_gdppc_sum` for use as our metric of "article power" in the edgelist of coauthor pairs. 


```python
%%time

import itertools
import pandas as pd 

author_pair_list = list(itertools.chain.from_iterable([
    list(itertools.combinations(author_df[author_df['pub_id']==pub_id].index,2))
    for pub_id in set(author_df['pub_id'])
]))

author_pairs_newindex = pd.DataFrame(index=pd.MultiIndex.from_tuples(author_pair_list, names=('n1', 'n2'))).reset_index()
authors_articles = pd.merge(author_df,article_df,how='left',on='pub_id').reset_index()
author_article_node1 = pd.merge(author_pairs_newindex, authors_articles, how='left', left_on='n1', right_on='index')
author_article_country_node1 = pd.merge(author_article_node1, country_stats, how='left', left_on='country_code', right_on='Country Code')
author_article_country_node1['cites_norm_gdppc_x'] = author_article_country_node1.apply(lambda row: row['cites_per_coauthor'] / row['log_gdppc'], axis=1)
author_article_node2 = pd.merge(author_article_country_node1, authors_articles, how='left', left_on='n2', right_on='index')

author_pairs = pd.merge(author_article_node2, country_stats, how='left', left_on='country_code_y', right_on='Country Code')
author_pairs['cites_norm_gdppc_y'] =  author_pairs.apply(lambda row: row['cites_per_coauthor_y'] / row['log_gdppc_y'], axis=1)

print('author pairs count:')
print(author_pairs)

country_pairs_count = pd.DataFrame(author_pairs, columns=['country_code_x','country_code_y']).value_counts(subset=['country_code_x','country_code_y'])\
                        .reset_index(name='count').rename(columns={'country_code_x':'node1','country_code_y':'node2'})

print('\ncountry pairs count:')
print(country_pairs_count)

ig_pairs_count = pd.DataFrame(author_pairs, columns=['Income group_x','Income group_y']).value_counts(subset=['Income group_x','Income group_y'])\
                   .reset_index(name='count').rename(columns={'Income group_x':'node1','Income group_y':'node2'})

print('\nincome group pairs count:')
print(ig_pairs_count)

country_pairs_norm = author_pairs.groupby(['country_code_x','country_code_y']).aggregate({'cites_norm_gdppc_x': 'sum', 'cites_norm_gdppc_y': 'sum'})\
                                 .reset_index().rename(columns={'country_code_x':'node1','country_code_y':'node2'})
country_pairs_norm['cites_norm_gdppc_sum'] = country_pairs_norm.apply(lambda row: (row['cites_norm_gdppc_x'] + row['cites_norm_gdppc_y']), axis=1)
country_pairs_norm.drop(['cites_norm_gdppc_x','cites_norm_gdppc_y'], axis=1, inplace=True)

print('\ncountry pairs normalized:')
print(country_pairs_norm.sort_values('cites_norm_gdppc_sum', ascending=False))

ig_pairs_norm = author_pairs.groupby(['Income group_x','Income group_y']).aggregate({'cites_norm_gdppc_x': 'sum', 'cites_norm_gdppc_y': 'sum'})\
                            .reset_index().rename(columns={'Income group_x':'node1','Income group_y':'node2'})
ig_pairs_norm['cites_norm_gdppc_sum'] = ig_pairs_norm.apply(lambda row: (row['cites_norm_gdppc_x'] + row['cites_norm_gdppc_y']), axis=1)
ig_pairs_norm.drop(['cites_norm_gdppc_x','cites_norm_gdppc_y'], axis=1, inplace=True)

print('\nincome group pairs normalized:')
print(ig_pairs_norm.sort_values('cites_norm_gdppc_sum', ascending=False))
```

    author pairs count:
              n1    n2  index_x                  pub_id_x country_code_x  \
    0       3095  3096     3095  64d2f92aadb21da659adc958            JPN   
    1       8954  8955     8954  64d2fce1adb21da659af9cfd            CHN   
    2       8954  8956     8954  64d2fce1adb21da659af9cfd            CHN   
    3       8954  8957     8954  64d2fce1adb21da659af9cfd            CHN   
    4       8955  8956     8955  64d2fce1adb21da659af9cfd            CHN   
    ...      ...   ...      ...                       ...            ...   
    100590  2909  2911     2909  64d2f8f7adb21da659adaf1f            CHN   
    100591  2909  2912     2909  64d2f8f7adb21da659adaf1f            CHN   
    100592  2910  2911     2910  64d2f8f7adb21da659adaf1f            CHN   
    100593  2910  2912     2910  64d2f8f7adb21da659adaf1f            CHN   
    100594  2911  2912     2911  64d2f8f7adb21da659adaf1f            CHN   
    
           author_position_x  pub_year_x  cited_by_count_x  coauthor_count_x  \
    0                  first        2023                 0                 2   
    1                  first        2022                 1                 4   
    2                  first        2022                 1                 4   
    3                  first        2022                 1                 4   
    4                 middle        2022                 1                 4   
    ...                  ...         ...               ...               ...   
    100590            middle        2018                28                 5   
    100591            middle        2018                28                 5   
    100592            middle        2018                28                 5   
    100593            middle        2018                28                 5   
    100594            middle        2018                28                 5   
    
            cites_per_coauthor_x  ... pub_year_y cited_by_count_y  \
    0                   0.010000  ...       2023                0   
    1                   0.083333  ...       2022                1   
    2                   0.083333  ...       2022                1   
    3                   0.083333  ...       2022                1   
    4                   0.083333  ...       2022                1   
    ...                      ...  ...        ...              ...   
    100590              1.400000  ...       2018               28   
    100591              1.400000  ...       2018               28   
    100592              1.400000  ...       2018               28   
    100593              1.400000  ...       2018               28   
    100594              1.400000  ...       2018               28   
    
           coauthor_count_y  cites_per_coauthor_y  Country Code_y  Country_y  \
    0                     2              0.010000             JPN      Japan   
    1                     4              0.083333             CHN      China   
    2                     4              0.083333             CHN      China   
    3                     4              0.083333             CHN      China   
    4                     4              0.083333             CHN      China   
    ...                 ...                   ...             ...        ...   
    100590                5              1.400000             CHN      China   
    100591                5              1.400000             CHN      China   
    100592                5              1.400000             CHN      China   
    100593                5              1.400000             CHN      China   
    100594                5              1.400000             CHN      China   
    
                 Income group_y GDP per capita(US$)_y log_gdppc_y  \
    0               High income          33815.317273   10.428669   
    1       Upper middle income          12720.215640    9.450948   
    2       Upper middle income          12720.215640    9.450948   
    3       Upper middle income          12720.215640    9.450948   
    4       Upper middle income          12720.215640    9.450948   
    ...                     ...                   ...         ...   
    100590  Upper middle income          12720.215640    9.450948   
    100591  Upper middle income          12720.215640    9.450948   
    100592  Upper middle income          12720.215640    9.450948   
    100593  Upper middle income          12720.215640    9.450948   
    100594  Upper middle income          12720.215640    9.450948   
    
           cites_norm_gdppc_y  
    0                0.000959  
    1                0.008817  
    2                0.008817  
    3                0.008817  
    4                0.008817  
    ...                   ...  
    100590           0.148133  
    100591           0.148133  
    100592           0.148133  
    100593           0.148133  
    100594           0.148133  
    
    [100595 rows x 30 columns]
    
    country pairs count:
         node1 node2  count
    0      CHN   CHN  26834
    1      USA   USA  12674
    2      ITA   ITA   2900
    3      BRA   BRA   2350
    4      DEU   DEU   2305
    ...    ...   ...    ...
    2326   JAM   TTO      1
    2327   JAM   ZAF      1
    2328   JOR   ITA      1
    2329   JPN   GRC      1
    2330   IRL   ECU      1
    
    [2331 rows x 3 columns]
    
    income group pairs count:
                      node1                node2  count
    0           High income          High income  51444
    1   Upper middle income  Upper middle income  32945
    2   Upper middle income          High income   4275
    3   Lower middle income  Lower middle income   3842
    4           High income  Upper middle income   3560
    5   Lower middle income          High income   1308
    6           High income  Lower middle income   1059
    7   Upper middle income  Lower middle income    374
    8   Lower middle income  Upper middle income    340
    9            Low income          High income    127
    10          High income           Low income    116
    11           Low income           Low income    109
    12           Low income  Lower middle income     39
    13  Lower middle income           Low income     39
    14  Upper middle income           Low income     34
    15           Low income  Upper middle income     24
    
    country pairs normalized:
         node1 node2  cites_norm_gdppc_sum
    403    CHN   CHN           3075.408920
    2269   USA   USA           1821.410569
    1286   ITA   ITA            425.632196
    1117   IND   IND            399.144667
    579    DEU   DEU            324.914795
    ...    ...   ...                   ...
    1908   SAU   FIN              0.000428
    1901   SAU   CAN              0.000426
    57     AUS   CZE              0.000425
    2155   TWN   TWN              0.000000
    1043   GUF   GUF              0.000000
    
    [2331 rows x 3 columns]
    
    income group pairs normalized:
                      node1                node2  cites_norm_gdppc_sum
    0           High income          High income           6840.314383
    15  Upper middle income  Upper middle income           3989.325459
    10  Lower middle income  Lower middle income            805.639766
    12  Upper middle income          High income            531.158890
    3           High income  Upper middle income            382.804781
    8   Lower middle income          High income            225.119384
    2           High income  Lower middle income            141.671110
    11  Lower middle income  Upper middle income             69.928501
    14  Upper middle income  Lower middle income             47.068858
    4            Low income          High income             24.381623
    5            Low income           Low income             22.051275
    1           High income           Low income              8.964837
    7            Low income  Upper middle income              6.945942
    6            Low income  Lower middle income              3.435547
    13  Upper middle income           Low income              2.458214
    9   Lower middle income           Low income              2.074174
    CPU times: user 45 s, sys: 164 ms, total: 45.2 s
    Wall time: 45.6 s


## Aggregate data for network nodes

### Country Article Pipeline

The `country_article_pipeline` is similar to the original `article_pipeline` aggregation. However, it queries the *country codes* instead of the publication years. It also calculates this column:

$$\text{avg_cites_per_coauthor} = \frac{\text{cited_by_sum}}{\text{coauthor_count}}$$

This differs from the similar field in `article_pipeline` since this is aggregated for the entire country and the article/author-level granularity of normalization is not required for this higher level metric. Instead, the total citations for each country are normalized by the total number of coauthors for a country. 


```python
%%time

import pandas as pd
from iso3166 import countries

# pipeline to determine attributes for each article
country_article_pipeline = [
    {
        '$match': {
            '_id': {'$in': id_list},
            'type': 'article'
        }
    },
    {
        '$unwind': '$authorships'
    },
    {
        '$project': {
            '_id': 1,
            'type': 1,
            'cited_by_count': 1,
            'country_code': {
                '$arrayElemAt': ['$authorships.institutions.country_code', 0]
            }
        }
    },
    {
        '$match': {'country_code': {'$exists': True}}
    },
    {
        '$group': {
            '_id': '$country_code',
            'cited_by_sum': {'$sum': '$cited_by_count'},
            'coauthor_count': {'$sum': 1}
        }
    }
]

# Execute the aggregation pipeline
country_article_result = collection.aggregate(country_article_pipeline)

# article_result2.__dict__

country_article_results_list = []

# Iterate through the result and populate the list
for entry in country_article_result:
    try:
        country_article_results_list.append({
            'country_code': countries.get(entry['_id']).alpha3,
            'cited_by_sum': entry['cited_by_sum'],
            'coauthor_count': entry['coauthor_count']
        })
    except:
        continue

# Create a Pandas DataFrame from the results list
country_article_df = pd.DataFrame(country_article_results_list)
country_article_df['avg_cites_per_coauthor'] = country_article_df.apply(
    lambda row: row['cited_by_sum']/row['coauthor_count'], 
    axis=1
)
country_article_df.replace({'avg_cites_per_coauthor': 0.}, 0.01, inplace=True)
country_article_df = country_article_df.groupby('country_code').aggregate({
    'avg_cites_per_coauthor':'mean',
    'cited_by_sum':'sum',
    'coauthor_count':'sum'
}).reset_index()

# Display the DataFrame
print(country_article_df.sort_values('avg_cites_per_coauthor', ascending=False))
```

        country_code  avg_cites_per_coauthor  cited_by_sum  coauthor_count
    39           EST              172.333333          2068              12
    139          ZWE              149.000000           447               3
    42           FJI              143.000000           143               1
    23           CIV              143.000000           143               1
    29           CUB              107.333333           644               6
    ..           ...                     ...           ...             ...
    90           NCL                0.010000             0               2
    86           MTQ                0.010000             0               1
    17           BRB                0.010000             0               1
    27           CPV                0.010000             0               1
    0            AFG                0.010000             0               1
    
    [140 rows x 4 columns]
    CPU times: user 28.9 ms, sys: 4.82 ms, total: 33.8 ms
    Wall time: 239 ms



```python
# This is a QAQC cell. These country codes are not merging properly with the GDP data. 
# Just needs some more data cleaning, but we'll ignore it for now....
# missing country associations

[ c for c in country_article_df['country_code'] if c not in list(country_article_df.merge(country_stats, how='inner', left_on='country_code', right_on='Country Code')['country_code']) ]
```




    ['GLP', 'GUF', 'MTQ', 'TWN', 'VEN']



### Node Attributes

This section parses the country article pipeline result into dicts readable by `networkx` to assign node charateristics. Attributes are parsed for graphs of the country network, and the income group network. 


```python
%%time 

from pprint import pprint
import pandas as pd

country_attrs = pd.merge(country_article_df, country_stats, how='left', left_on='country_code', right_on='Country Code')

country_node_attrs = {
  I: {
        'coauthor_count':int(country_attrs[country_attrs['country_code']==I]['coauthor_count']),
        'cited_by_sum':int(country_attrs[country_attrs['country_code']==I]['cited_by_sum']),
        'avg_cites_per_coauthor':round(float(country_attrs[country_attrs['country_code']==I]['avg_cites_per_coauthor']),3),
        'Income group': list(country_attrs[country_attrs['country_code']==I]['Income group'])[0]
     }
  for I in country_article_df['country_code']
}

ig_attrs = pd.merge(country_article_df, country_stats, how='left', left_on='country_code', right_on='Country Code') \
             .drop(columns={'Country Code','Country','country_code'}) \
             .groupby('Income group').agg({
                'coauthor_count':'sum',
                'cited_by_sum':'sum',
                'avg_cites_per_coauthor':'mean'
             }).reset_index()

ig_node_attrs = { 
  I: {
        'coauthor_count':int(ig_attrs[ig_attrs['Income group']==I]['coauthor_count']),
        'cited_by_sum':int(ig_attrs[ig_attrs['Income group']==I]['cited_by_sum']),
        'avg_cites_per_coauthor':round(float(ig_attrs[ig_attrs['Income group']==I]['avg_cites_per_coauthor']),3),
     }
  for I in ig_attrs['Income group']
}

# pprint(country_node_attrs)
pprint(ig_node_attrs)
```

    {'High income': {'avg_cites_per_coauthor': 29.674,
                     'cited_by_sum': 500098,
                     'coauthor_count': 16826},
     'Low income': {'avg_cites_per_coauthor': 13.645,
                    'cited_by_sum': 2869,
                    'coauthor_count': 89},
     'Lower middle income': {'avg_cites_per_coauthor': 27.032,
                             'cited_by_sum': 46250,
                             'coauthor_count': 2022},
     'Upper middle income': {'avg_cites_per_coauthor': 21.29,
                             'cited_by_sum': 264351,
                             'coauthor_count': 12093}}
    CPU times: user 198 ms, sys: 24.8 ms, total: 222 ms
    Wall time: 206 ms


## Plots

### Network Plots


```python
import matplotlib.pyplot as plt
import networkx as nx
from pprint import pprint

country_graph = nx.from_pandas_edgelist(df=country_pairs_norm[country_pairs_norm['cites_norm_gdppc_sum']>1],
                                        source='node1', target='node2', edge_attr='cites_norm_gdppc_sum')
nx.set_node_attributes(country_graph, country_node_attrs)

nx.write_gexf(country_graph, f"gephi/country_graph-{target_concept}-{n_samples}.gexf")

# Set the background color to white
plt.rcParams['axes.facecolor'] = 'white'

# Expand the figure size for better visibility
plt.figure(figsize=(10, 8))

# Draw the graph with node sizes and red edges
pos = nx.spring_layout(country_graph, seed=42, k=10, iterations=50)
labels = {e: round(country_graph.edges[e]['cites_norm_gdppc_sum'],3) for e in country_graph.edges}
color_code = {
    'High income': 'blue',
    'Upper middle income': 'green',
    'Lower middle income': 'yellow',
    'Low income': 'red'
}
node_color = [ 'gray' if c is None else c for c in 
                [ color_code.get(country_graph.nodes[node]['Income group']) for node in country_graph.nodes() ]
             ]
node_size = [ country_graph.nodes[node]['avg_cites_per_coauthor'] * 50 for node in country_graph.nodes() ]

# pprint(labels)
# pprint(country_node_attrs)

nx.draw(country_graph, pos, node_size=node_size, node_color=node_color, with_labels=True)
nx.draw_networkx_edge_labels(country_graph, pos, edge_labels=labels, label_pos=0.5, 
                             horizontalalignment='right', verticalalignment='top')

# Show the graph
plt.show()
```


    
![png](output_29_0.png)
    



```python
import matplotlib.pyplot as plt
import networkx as nx
from pprint import pprint

ig_graph = nx.from_pandas_edgelist(df=ig_pairs_norm, source='node1', target='node2', edge_attr='cites_norm_gdppc_sum')
nx.set_node_attributes(ig_graph, ig_node_attrs)

nx.write_gexf(ig_graph, f"gephi/ig_graph-{target_concept}-{n_samples}.gexf")

# Set the background color to white
plt.rcParams['axes.facecolor'] = 'white'

# Expand the figure size for better visibility
plt.figure(figsize=(10, 8))

# Draw the graph with node sizes and red edges
pos = nx.spring_layout(ig_graph, seed=42, k=10, iterations=50)
labels = {e: round(ig_graph.edges[e]['cites_norm_gdppc_sum'],3) for e in ig_graph.edges}
color_code = {
    'High income': 'blue', 
    'Upper middle income': 'green',
    'Lower middle income': 'yellow',
    'Low income': 'red'
}
node_color = [ 'gray' if c is None else c for c in 
                [ color_code.get(node) for node in ig_graph.nodes() ]
             ]
node_size = [ig_graph.nodes[node]['avg_cites_per_coauthor'] * 50 for node in ig_graph.nodes()]

pprint(labels)
pprint(ig_node_attrs)

nx.draw(ig_graph, pos, node_size=node_size, node_color=node_color, with_labels=False)
nx.draw_networkx_edge_labels(ig_graph, pos, edge_labels=labels, label_pos=0.5, 
                             horizontalalignment='right', verticalalignment='top')

# Show the graph
plt.show()
```

    {('High income', 'High income'): 6840.314,
     ('High income', 'Low income'): 24.382,
     ('High income', 'Lower middle income'): 225.119,
     ('High income', 'Upper middle income'): 531.159,
     ('Low income', 'Low income'): 22.051,
     ('Low income', 'Lower middle income'): 2.074,
     ('Low income', 'Upper middle income'): 2.458,
     ('Lower middle income', 'Lower middle income'): 805.64,
     ('Lower middle income', 'Upper middle income'): 47.069,
     ('Upper middle income', 'Upper middle income'): 3989.325}
    {'High income': {'avg_cites_per_coauthor': 29.674,
                     'cited_by_sum': 500098,
                     'coauthor_count': 16826},
     'Low income': {'avg_cites_per_coauthor': 13.645,
                    'cited_by_sum': 2869,
                    'coauthor_count': 89},
     'Lower middle income': {'avg_cites_per_coauthor': 27.032,
                             'cited_by_sum': 46250,
                             'coauthor_count': 2022},
     'Upper middle income': {'avg_cites_per_coauthor': 21.29,
                             'cited_by_sum': 264351,
                             'coauthor_count': 12093}}



    
![png](output_30_1.png)
    


### Bar Plots


```python
plotdf = pd.merge(country_article_df, country_stats, how='left', right_on='Country Code', left_on='country_code') \
           .drop(columns={'Country Code','Country','country_code'}) \
           .groupby('Income group').agg({'coauthor_count':'sum','cited_by_sum':'sum','avg_cites_per_coauthor':'mean'}) \
           .reset_index().melt(id_vars = ['Income group'], value_vars=['coauthor_count','cited_by_sum','avg_cites_per_coauthor'])

# plotdf
```


```python
import plotly.express as px

fig = px.bar(plotdf[plotdf['variable']=='coauthor_count'], x="Income group", y='value', color='variable', log_y=True,
             category_orders={'Income group':['High income', 'Upper middle income', 'Lower middle income','Low income']}, width=1000, height=800)

fig.write_html(f"plots/coauthor_counts_ig-{target_concept}-{n_samples}.html")

fig.show()
```


        <script type="text/javascript">
        window.PlotlyConfig = {MathJaxConfig: 'local'};
        if (window.MathJax && window.MathJax.Hub && window.MathJax.Hub.Config) {window.MathJax.Hub.Config({SVG: {font: "STIX-Web"}});}
        if (typeof require !== 'undefined') {
        require.undef("plotly");
        define('plotly', function(require, exports, module) {
            /**
* plotly.js v2.24.1
* Copyright 2012-2023, Plotly, Inc.
* All rights reserved.
* Licensed under the MIT license
*/
/*! For license information please see plotly.min.js.LICENSE.txt */
        });
        require(['plotly'], function(Plotly) {
            window._Plotly = Plotly;
        });
        }
        </script>




<div>                            <div id="9b7de83e-d189-49f1-9f25-3147efcfab94" class="plotly-graph-div" style="height:800px; width:1000px;"></div>            <script type="text/javascript">                require(["plotly"], function(Plotly) {                    window.PLOTLYENV=window.PLOTLYENV || {};                                    if (document.getElementById("9b7de83e-d189-49f1-9f25-3147efcfab94")) {                    Plotly.newPlot(                        "9b7de83e-d189-49f1-9f25-3147efcfab94",                        [{"alignmentgroup":"True","hovertemplate":"variable=coauthor_count\u003cbr\u003eIncome group=%{x}\u003cbr\u003evalue=%{y}\u003cextra\u003e\u003c\u002fextra\u003e","legendgroup":"coauthor_count","marker":{"color":"#636efa","pattern":{"shape":""}},"name":"coauthor_count","offsetgroup":"coauthor_count","orientation":"v","showlegend":true,"textposition":"auto","x":["High income","Low income","Lower middle income","Upper middle income"],"xaxis":"x","y":[16826.0,89.0,2022.0,12093.0],"yaxis":"y","type":"bar"}],                        {"template":{"data":{"histogram2dcontour":[{"type":"histogram2dcontour","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"choropleth":[{"type":"choropleth","colorbar":{"outlinewidth":0,"ticks":""}}],"histogram2d":[{"type":"histogram2d","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"heatmap":[{"type":"heatmap","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"heatmapgl":[{"type":"heatmapgl","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"contourcarpet":[{"type":"contourcarpet","colorbar":{"outlinewidth":0,"ticks":""}}],"contour":[{"type":"contour","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"surface":[{"type":"surface","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"mesh3d":[{"type":"mesh3d","colorbar":{"outlinewidth":0,"ticks":""}}],"scatter":[{"fillpattern":{"fillmode":"overlay","size":10,"solidity":0.2},"type":"scatter"}],"parcoords":[{"type":"parcoords","line":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterpolargl":[{"type":"scatterpolargl","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"bar":[{"error_x":{"color":"#2a3f5f"},"error_y":{"color":"#2a3f5f"},"marker":{"line":{"color":"#E5ECF6","width":0.5},"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"bar"}],"scattergeo":[{"type":"scattergeo","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterpolar":[{"type":"scatterpolar","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"histogram":[{"marker":{"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"histogram"}],"scattergl":[{"type":"scattergl","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatter3d":[{"type":"scatter3d","line":{"colorbar":{"outlinewidth":0,"ticks":""}},"marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scattermapbox":[{"type":"scattermapbox","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterternary":[{"type":"scatterternary","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scattercarpet":[{"type":"scattercarpet","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"carpet":[{"aaxis":{"endlinecolor":"#2a3f5f","gridcolor":"white","linecolor":"white","minorgridcolor":"white","startlinecolor":"#2a3f5f"},"baxis":{"endlinecolor":"#2a3f5f","gridcolor":"white","linecolor":"white","minorgridcolor":"white","startlinecolor":"#2a3f5f"},"type":"carpet"}],"table":[{"cells":{"fill":{"color":"#EBF0F8"},"line":{"color":"white"}},"header":{"fill":{"color":"#C8D4E3"},"line":{"color":"white"}},"type":"table"}],"barpolar":[{"marker":{"line":{"color":"#E5ECF6","width":0.5},"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"barpolar"}],"pie":[{"automargin":true,"type":"pie"}]},"layout":{"autotypenumbers":"strict","colorway":["#636efa","#EF553B","#00cc96","#ab63fa","#FFA15A","#19d3f3","#FF6692","#B6E880","#FF97FF","#FECB52"],"font":{"color":"#2a3f5f"},"hovermode":"closest","hoverlabel":{"align":"left"},"paper_bgcolor":"white","plot_bgcolor":"#E5ECF6","polar":{"bgcolor":"#E5ECF6","angularaxis":{"gridcolor":"white","linecolor":"white","ticks":""},"radialaxis":{"gridcolor":"white","linecolor":"white","ticks":""}},"ternary":{"bgcolor":"#E5ECF6","aaxis":{"gridcolor":"white","linecolor":"white","ticks":""},"baxis":{"gridcolor":"white","linecolor":"white","ticks":""},"caxis":{"gridcolor":"white","linecolor":"white","ticks":""}},"coloraxis":{"colorbar":{"outlinewidth":0,"ticks":""}},"colorscale":{"sequential":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]],"sequentialminus":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]],"diverging":[[0,"#8e0152"],[0.1,"#c51b7d"],[0.2,"#de77ae"],[0.3,"#f1b6da"],[0.4,"#fde0ef"],[0.5,"#f7f7f7"],[0.6,"#e6f5d0"],[0.7,"#b8e186"],[0.8,"#7fbc41"],[0.9,"#4d9221"],[1,"#276419"]]},"xaxis":{"gridcolor":"white","linecolor":"white","ticks":"","title":{"standoff":15},"zerolinecolor":"white","automargin":true,"zerolinewidth":2},"yaxis":{"gridcolor":"white","linecolor":"white","ticks":"","title":{"standoff":15},"zerolinecolor":"white","automargin":true,"zerolinewidth":2},"scene":{"xaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2},"yaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2},"zaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2}},"shapedefaults":{"line":{"color":"#2a3f5f"}},"annotationdefaults":{"arrowcolor":"#2a3f5f","arrowhead":0,"arrowwidth":1},"geo":{"bgcolor":"white","landcolor":"#E5ECF6","subunitcolor":"white","showland":true,"showlakes":true,"lakecolor":"white"},"title":{"x":0.05},"mapbox":{"style":"light"}}},"xaxis":{"anchor":"y","domain":[0.0,1.0],"title":{"text":"Income group"},"categoryorder":"array","categoryarray":["High income","Upper middle income","Lower middle income","Low income"]},"yaxis":{"anchor":"x","domain":[0.0,1.0],"title":{"text":"value"},"type":"log"},"legend":{"title":{"text":"variable"},"tracegroupgap":0},"margin":{"t":60},"barmode":"relative","height":800,"width":1000},                        {"responsive": true}                    ).then(function(){

var gd = document.getElementById('9b7de83e-d189-49f1-9f25-3147efcfab94');
var x = new MutationObserver(function (mutations, observer) {{
        var display = window.getComputedStyle(gd).display;
        if (!display || display === 'none') {{
            console.log([gd, 'removed!']);
            Plotly.purge(gd);
            observer.disconnect();
        }}
}});

// Listen for the removal of the full notebook cells
var notebookContainer = gd.closest('#notebook-container');
if (notebookContainer) {{
    x.observe(notebookContainer, {childList: true});
}}

// Listen for the clearing of the current output cell
var outputEl = gd.closest('.output');
if (outputEl) {{
    x.observe(outputEl, {childList: true});
}}

                        })                };                });            </script>        </div>



```python
import plotly.express as px

fig = px.bar(plotdf[plotdf['variable']=='cited_by_sum'], x="Income group", y='value', color='variable', log_y=True,
             category_orders={'Income group':['High income', 'Upper middle income', 'Lower middle income','Low income']}, width=1000, height=800)

fig.write_html(f"plots/cited_by_sum_ig-{target_concept}-{n_samples}.html")

fig.show()
```


<div>                            <div id="6a1d366d-9592-4ec1-b1ed-bb635bb70a0b" class="plotly-graph-div" style="height:800px; width:1000px;"></div>            <script type="text/javascript">                require(["plotly"], function(Plotly) {                    window.PLOTLYENV=window.PLOTLYENV || {};                                    if (document.getElementById("6a1d366d-9592-4ec1-b1ed-bb635bb70a0b")) {                    Plotly.newPlot(                        "6a1d366d-9592-4ec1-b1ed-bb635bb70a0b",                        [{"alignmentgroup":"True","hovertemplate":"variable=cited_by_sum\u003cbr\u003eIncome group=%{x}\u003cbr\u003evalue=%{y}\u003cextra\u003e\u003c\u002fextra\u003e","legendgroup":"cited_by_sum","marker":{"color":"#636efa","pattern":{"shape":""}},"name":"cited_by_sum","offsetgroup":"cited_by_sum","orientation":"v","showlegend":true,"textposition":"auto","x":["High income","Low income","Lower middle income","Upper middle income"],"xaxis":"x","y":[500098.0,2869.0,46250.0,264351.0],"yaxis":"y","type":"bar"}],                        {"template":{"data":{"histogram2dcontour":[{"type":"histogram2dcontour","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"choropleth":[{"type":"choropleth","colorbar":{"outlinewidth":0,"ticks":""}}],"histogram2d":[{"type":"histogram2d","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"heatmap":[{"type":"heatmap","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"heatmapgl":[{"type":"heatmapgl","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"contourcarpet":[{"type":"contourcarpet","colorbar":{"outlinewidth":0,"ticks":""}}],"contour":[{"type":"contour","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"surface":[{"type":"surface","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"mesh3d":[{"type":"mesh3d","colorbar":{"outlinewidth":0,"ticks":""}}],"scatter":[{"fillpattern":{"fillmode":"overlay","size":10,"solidity":0.2},"type":"scatter"}],"parcoords":[{"type":"parcoords","line":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterpolargl":[{"type":"scatterpolargl","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"bar":[{"error_x":{"color":"#2a3f5f"},"error_y":{"color":"#2a3f5f"},"marker":{"line":{"color":"#E5ECF6","width":0.5},"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"bar"}],"scattergeo":[{"type":"scattergeo","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterpolar":[{"type":"scatterpolar","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"histogram":[{"marker":{"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"histogram"}],"scattergl":[{"type":"scattergl","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatter3d":[{"type":"scatter3d","line":{"colorbar":{"outlinewidth":0,"ticks":""}},"marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scattermapbox":[{"type":"scattermapbox","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterternary":[{"type":"scatterternary","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scattercarpet":[{"type":"scattercarpet","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"carpet":[{"aaxis":{"endlinecolor":"#2a3f5f","gridcolor":"white","linecolor":"white","minorgridcolor":"white","startlinecolor":"#2a3f5f"},"baxis":{"endlinecolor":"#2a3f5f","gridcolor":"white","linecolor":"white","minorgridcolor":"white","startlinecolor":"#2a3f5f"},"type":"carpet"}],"table":[{"cells":{"fill":{"color":"#EBF0F8"},"line":{"color":"white"}},"header":{"fill":{"color":"#C8D4E3"},"line":{"color":"white"}},"type":"table"}],"barpolar":[{"marker":{"line":{"color":"#E5ECF6","width":0.5},"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"barpolar"}],"pie":[{"automargin":true,"type":"pie"}]},"layout":{"autotypenumbers":"strict","colorway":["#636efa","#EF553B","#00cc96","#ab63fa","#FFA15A","#19d3f3","#FF6692","#B6E880","#FF97FF","#FECB52"],"font":{"color":"#2a3f5f"},"hovermode":"closest","hoverlabel":{"align":"left"},"paper_bgcolor":"white","plot_bgcolor":"#E5ECF6","polar":{"bgcolor":"#E5ECF6","angularaxis":{"gridcolor":"white","linecolor":"white","ticks":""},"radialaxis":{"gridcolor":"white","linecolor":"white","ticks":""}},"ternary":{"bgcolor":"#E5ECF6","aaxis":{"gridcolor":"white","linecolor":"white","ticks":""},"baxis":{"gridcolor":"white","linecolor":"white","ticks":""},"caxis":{"gridcolor":"white","linecolor":"white","ticks":""}},"coloraxis":{"colorbar":{"outlinewidth":0,"ticks":""}},"colorscale":{"sequential":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]],"sequentialminus":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]],"diverging":[[0,"#8e0152"],[0.1,"#c51b7d"],[0.2,"#de77ae"],[0.3,"#f1b6da"],[0.4,"#fde0ef"],[0.5,"#f7f7f7"],[0.6,"#e6f5d0"],[0.7,"#b8e186"],[0.8,"#7fbc41"],[0.9,"#4d9221"],[1,"#276419"]]},"xaxis":{"gridcolor":"white","linecolor":"white","ticks":"","title":{"standoff":15},"zerolinecolor":"white","automargin":true,"zerolinewidth":2},"yaxis":{"gridcolor":"white","linecolor":"white","ticks":"","title":{"standoff":15},"zerolinecolor":"white","automargin":true,"zerolinewidth":2},"scene":{"xaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2},"yaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2},"zaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2}},"shapedefaults":{"line":{"color":"#2a3f5f"}},"annotationdefaults":{"arrowcolor":"#2a3f5f","arrowhead":0,"arrowwidth":1},"geo":{"bgcolor":"white","landcolor":"#E5ECF6","subunitcolor":"white","showland":true,"showlakes":true,"lakecolor":"white"},"title":{"x":0.05},"mapbox":{"style":"light"}}},"xaxis":{"anchor":"y","domain":[0.0,1.0],"title":{"text":"Income group"},"categoryorder":"array","categoryarray":["High income","Upper middle income","Lower middle income","Low income"]},"yaxis":{"anchor":"x","domain":[0.0,1.0],"title":{"text":"value"},"type":"log"},"legend":{"title":{"text":"variable"},"tracegroupgap":0},"margin":{"t":60},"barmode":"relative","height":800,"width":1000},                        {"responsive": true}                    ).then(function(){

var gd = document.getElementById('6a1d366d-9592-4ec1-b1ed-bb635bb70a0b');
var x = new MutationObserver(function (mutations, observer) {{
        var display = window.getComputedStyle(gd).display;
        if (!display || display === 'none') {{
            console.log([gd, 'removed!']);
            Plotly.purge(gd);
            observer.disconnect();
        }}
}});

// Listen for the removal of the full notebook cells
var notebookContainer = gd.closest('#notebook-container');
if (notebookContainer) {{
    x.observe(notebookContainer, {childList: true});
}}

// Listen for the clearing of the current output cell
var outputEl = gd.closest('.output');
if (outputEl) {{
    x.observe(outputEl, {childList: true});
}}

                        })                };                });            </script>        </div>



```python
import plotly.express as px

fig = px.bar(plotdf[plotdf['variable']=='avg_cites_per_coauthor'], x="Income group", y='value', color='variable', 
             category_orders={'Income group':['High income', 'Upper middle income', 'Lower middle income','Low income']}, width=1000, height=800)

fig.write_html(f"plots/avg_cites_per_coauthor_ig-{target_concept}-{n_samples}.html")

fig.show()
```


<div>                            <div id="796c9b4f-f18e-4311-8e47-cbe1e727ea98" class="plotly-graph-div" style="height:800px; width:1000px;"></div>            <script type="text/javascript">                require(["plotly"], function(Plotly) {                    window.PLOTLYENV=window.PLOTLYENV || {};                                    if (document.getElementById("796c9b4f-f18e-4311-8e47-cbe1e727ea98")) {                    Plotly.newPlot(                        "796c9b4f-f18e-4311-8e47-cbe1e727ea98",                        [{"alignmentgroup":"True","hovertemplate":"variable=avg_cites_per_coauthor\u003cbr\u003eIncome group=%{x}\u003cbr\u003evalue=%{y}\u003cextra\u003e\u003c\u002fextra\u003e","legendgroup":"avg_cites_per_coauthor","marker":{"color":"#636efa","pattern":{"shape":""}},"name":"avg_cites_per_coauthor","offsetgroup":"avg_cites_per_coauthor","orientation":"v","showlegend":true,"textposition":"auto","x":["High income","Low income","Lower middle income","Upper middle income"],"xaxis":"x","y":[29.674369148839418,13.64501461988304,27.032012119868973,21.289550780941763],"yaxis":"y","type":"bar"}],                        {"template":{"data":{"histogram2dcontour":[{"type":"histogram2dcontour","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"choropleth":[{"type":"choropleth","colorbar":{"outlinewidth":0,"ticks":""}}],"histogram2d":[{"type":"histogram2d","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"heatmap":[{"type":"heatmap","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"heatmapgl":[{"type":"heatmapgl","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"contourcarpet":[{"type":"contourcarpet","colorbar":{"outlinewidth":0,"ticks":""}}],"contour":[{"type":"contour","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"surface":[{"type":"surface","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"mesh3d":[{"type":"mesh3d","colorbar":{"outlinewidth":0,"ticks":""}}],"scatter":[{"fillpattern":{"fillmode":"overlay","size":10,"solidity":0.2},"type":"scatter"}],"parcoords":[{"type":"parcoords","line":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterpolargl":[{"type":"scatterpolargl","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"bar":[{"error_x":{"color":"#2a3f5f"},"error_y":{"color":"#2a3f5f"},"marker":{"line":{"color":"#E5ECF6","width":0.5},"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"bar"}],"scattergeo":[{"type":"scattergeo","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterpolar":[{"type":"scatterpolar","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"histogram":[{"marker":{"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"histogram"}],"scattergl":[{"type":"scattergl","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatter3d":[{"type":"scatter3d","line":{"colorbar":{"outlinewidth":0,"ticks":""}},"marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scattermapbox":[{"type":"scattermapbox","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterternary":[{"type":"scatterternary","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scattercarpet":[{"type":"scattercarpet","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"carpet":[{"aaxis":{"endlinecolor":"#2a3f5f","gridcolor":"white","linecolor":"white","minorgridcolor":"white","startlinecolor":"#2a3f5f"},"baxis":{"endlinecolor":"#2a3f5f","gridcolor":"white","linecolor":"white","minorgridcolor":"white","startlinecolor":"#2a3f5f"},"type":"carpet"}],"table":[{"cells":{"fill":{"color":"#EBF0F8"},"line":{"color":"white"}},"header":{"fill":{"color":"#C8D4E3"},"line":{"color":"white"}},"type":"table"}],"barpolar":[{"marker":{"line":{"color":"#E5ECF6","width":0.5},"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"barpolar"}],"pie":[{"automargin":true,"type":"pie"}]},"layout":{"autotypenumbers":"strict","colorway":["#636efa","#EF553B","#00cc96","#ab63fa","#FFA15A","#19d3f3","#FF6692","#B6E880","#FF97FF","#FECB52"],"font":{"color":"#2a3f5f"},"hovermode":"closest","hoverlabel":{"align":"left"},"paper_bgcolor":"white","plot_bgcolor":"#E5ECF6","polar":{"bgcolor":"#E5ECF6","angularaxis":{"gridcolor":"white","linecolor":"white","ticks":""},"radialaxis":{"gridcolor":"white","linecolor":"white","ticks":""}},"ternary":{"bgcolor":"#E5ECF6","aaxis":{"gridcolor":"white","linecolor":"white","ticks":""},"baxis":{"gridcolor":"white","linecolor":"white","ticks":""},"caxis":{"gridcolor":"white","linecolor":"white","ticks":""}},"coloraxis":{"colorbar":{"outlinewidth":0,"ticks":""}},"colorscale":{"sequential":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]],"sequentialminus":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]],"diverging":[[0,"#8e0152"],[0.1,"#c51b7d"],[0.2,"#de77ae"],[0.3,"#f1b6da"],[0.4,"#fde0ef"],[0.5,"#f7f7f7"],[0.6,"#e6f5d0"],[0.7,"#b8e186"],[0.8,"#7fbc41"],[0.9,"#4d9221"],[1,"#276419"]]},"xaxis":{"gridcolor":"white","linecolor":"white","ticks":"","title":{"standoff":15},"zerolinecolor":"white","automargin":true,"zerolinewidth":2},"yaxis":{"gridcolor":"white","linecolor":"white","ticks":"","title":{"standoff":15},"zerolinecolor":"white","automargin":true,"zerolinewidth":2},"scene":{"xaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2},"yaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2},"zaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2}},"shapedefaults":{"line":{"color":"#2a3f5f"}},"annotationdefaults":{"arrowcolor":"#2a3f5f","arrowhead":0,"arrowwidth":1},"geo":{"bgcolor":"white","landcolor":"#E5ECF6","subunitcolor":"white","showland":true,"showlakes":true,"lakecolor":"white"},"title":{"x":0.05},"mapbox":{"style":"light"}}},"xaxis":{"anchor":"y","domain":[0.0,1.0],"title":{"text":"Income group"},"categoryorder":"array","categoryarray":["High income","Upper middle income","Lower middle income","Low income"]},"yaxis":{"anchor":"x","domain":[0.0,1.0],"title":{"text":"value"}},"legend":{"title":{"text":"variable"},"tracegroupgap":0},"margin":{"t":60},"barmode":"relative","height":800,"width":1000},                        {"responsive": true}                    ).then(function(){

var gd = document.getElementById('796c9b4f-f18e-4311-8e47-cbe1e727ea98');
var x = new MutationObserver(function (mutations, observer) {{
        var display = window.getComputedStyle(gd).display;
        if (!display || display === 'none') {{
            console.log([gd, 'removed!']);
            Plotly.purge(gd);
            observer.disconnect();
        }}
}});

// Listen for the removal of the full notebook cells
var notebookContainer = gd.closest('#notebook-container');
if (notebookContainer) {{
    x.observe(notebookContainer, {childList: true});
}}

// Listen for the clearing of the current output cell
var outputEl = gd.closest('.output');
if (outputEl) {{
    x.observe(outputEl, {childList: true});
}}

                        })                };                });            </script>        </div>


### Choropleth Plots


```python
import pandas as pd

choropleth_df = pd.merge(country_article_df, country_stats, how='left', left_on='country_code', right_on='Country Code')
```


```python
import plotly.express as px
import pandas as pd
import numpy as np

avg_avg_cites_per_coauthor = np.mean(choropleth_df['avg_cites_per_coauthor'])
max_avg_cites_per_coauthor = np.max(choropleth_df['avg_cites_per_coauthor'])

fig = px.choropleth(choropleth_df, locations="country_code",
                    color="avg_cites_per_coauthor",
                    range_color=(0,max_avg_cites_per_coauthor),
                    hover_name="Country",
                    width=1200, height=800,
                    color_continuous_scale=px.colors.diverging.Earth[::-1],
                    color_continuous_midpoint=avg_avg_cites_per_coauthor)

fig.update_layout(
    margin=dict(l=30, r=30, t=30, b=30),
    paper_bgcolor="LightSteelBlue",
)

fig.write_html(f"plots/avg_cites_per_coauthor_choropleth-{target_concept}-{n_samples}.html")

fig.show()
```


<div>                            <div id="e3b8c8df-c47c-4c65-8022-67a226b318af" class="plotly-graph-div" style="height:800px; width:1200px;"></div>            <script type="text/javascript">                require(["plotly"], function(Plotly) {                    window.PLOTLYENV=window.PLOTLYENV || {};                                    if (document.getElementById("e3b8c8df-c47c-4c65-8022-67a226b318af")) {                    Plotly.newPlot(                        "e3b8c8df-c47c-4c65-8022-67a226b318af",                        [{"coloraxis":"coloraxis","geo":"geo","hovertemplate":"\u003cb\u003e%{hovertext}\u003c\u002fb\u003e\u003cbr\u003e\u003cbr\u003ecountry_code=%{location}\u003cbr\u003eavg_cites_per_coauthor=%{z}\u003cextra\u003e\u003c\u002fextra\u003e","hovertext":["Afghanistan","Albania","United Arab Emirates","Argentina","Armenia","Australia","Austria","Belgium","Benin","Bangladesh","Bulgaria","Bahrain","Bosnia and Herzegovina","Belarus","Bermuda","Bolivia","Brazil","Barbados","Brunei Darussalam","Canada","Switzerland","Chile","China","C\u00f4te d\u2019Ivoire","Cameroon","Congo, Dem. Rep.","Colombia","Cabo Verde","Costa Rica","Cuba","Cyprus","Czechia","Germany","Denmark","Dominican Republic","Algeria","Ecuador","Egypt, Arab Rep.","Spain","Estonia","Ethiopia","Finland","Fiji","France","Faroe Islands","United Kingdom","Georgia","Ghana",null,"Greece","Greenland",null,"Guyana","Croatia","Hungary","Indonesia","India","Ireland","Iran, Islamic Rep.","Iraq","Iceland","Israel","Italy","Jamaica","Jordan","Japan","Kazakhstan","Kenya","Cambodia","Korea, Rep.","Kuwait","Lao PDR","Lebanon","Sri Lanka","Lithuania","Luxembourg","Latvia","Morocco","Monaco","Mexico","North Macedonia","Mali","Malta","Myanmar","Mongolia","Mozambique",null,"Malawi","Malaysia","Namibia","New Caledonia","Nigeria","Netherlands","Norway","Nepal","New Zealand","Oman","Pakistan","Panama","Peru","Philippines","Papua New Guinea","Poland","Portugal","West Bank and Gaza","Qatar","Romania","Russian Federation","Rwanda","Saudi Arabia","Sudan","Senegal","Singapore","Sierra Leone","Serbia","Slovak Republic","Slovenia","Sweden","Seychelles","Syrian Arab Republic","Chad","Thailand","Tajikistan","Turkmenistan","Trinidad and Tobago","Tunisia","T\u00fcrkiye",null,"Tanzania","Uganda","Ukraine","Uruguay","United States","Uzbekistan",null,"Vietnam","Kosovo","South Africa","Zambia","Zimbabwe"],"locations":["AFG","ALB","ARE","ARG","ARM","AUS","AUT","BEL","BEN","BGD","BGR","BHR","BIH","BLR","BMU","BOL","BRA","BRB","BRN","CAN","CHE","CHL","CHN","CIV","CMR","COD","COL","CPV","CRI","CUB","CYP","CZE","DEU","DNK","DOM","DZA","ECU","EGY","ESP","EST","ETH","FIN","FJI","FRA","FRO","GBR","GEO","GHA","GLP","GRC","GRL","GUF","GUY","HRV","HUN","IDN","IND","IRL","IRN","IRQ","ISL","ISR","ITA","JAM","JOR","JPN","KAZ","KEN","KHM","KOR","KWT","LAO","LBN","LKA","LTU","LUX","LVA","MAR","MCO","MEX","MKD","MLI","MLT","MMR","MNG","MOZ","MTQ","MWI","MYS","NAM","NCL","NGA","NLD","NOR","NPL","NZL","OMN","PAK","PAN","PER","PHL","PNG","POL","PRT","PSE","QAT","ROU","RUS","RWA","SAU","SDN","SEN","SGP","SLE","SRB","SVK","SVN","SWE","SYC","SYR","TCD","THA","TJK","TKM","TTO","TUN","TUR","TWN","TZA","UGA","UKR","URY","USA","UZB","VEN","VNM","XKX","ZAF","ZMB","ZWE"],"name":"","z":[0.01,8.0,16.45,44.82142857142857,2.0,39.17333333333333,48.95263157894737,28.773662551440328,10.090909090909092,34.26315789473684,7.1,0.01,0.5,10.0,8.5,4.0,26.182440136830103,0.01,36.0,29.16759776536313,42.017301038062286,17.535714285714285,22.073625549244454,143.0,3.740740740740741,1.0,16.528301886792452,0.01,32.375,107.33333333333333,60.23076923076923,20.488888888888887,42.99685204616999,33.19469026548673,1.0,12.764705882352942,13.0,15.728260869565217,26.440594059405942,172.33333333333334,51.25,25.22748815165877,143.0,27.108516483516482,62.5,28.73447946513849,32.375,21.403846153846153,3.0,20.80952380952381,26.333333333333332,15.0,76.0,13.08695652173913,42.698113207547166,5.615,26.57304964539007,21.93258426966292,15.193370165745856,5.730769230769231,23.133333333333333,25.52777777777778,26.73489932885906,27.75,10.96551724137931,20.109615384615385,1.6923076923076923,61.853658536585364,1.1666666666666667,17.20344827586207,29.714285714285715,7.0,26.333333333333332,51.875,14.416666666666666,6.0588235294117645,14.444444444444445,10.8125,1.0,20.575129533678755,5.166666666666667,9.0,23.0,4.5,22.666666666666668,14.6,0.01,23.666666666666668,22.306122448979593,4.5,0.01,10.049180327868852,26.811494252873562,31.114427860696516,84.86363636363636,22.790697674418606,12.375,26.609865470852018,9.5,5.2,15.975609756097562,0.01,14.061827956989248,30.468354430379748,3.0,24.318181818181817,8.303571428571429,6.930769230769231,10.8,18.350877192982455,15.666666666666666,12.0,39.60674157303371,0.01,22.408163265306122,21.157894736842106,49.484848484848484,36.09771986970684,31.0,7.0,2.0,14.064220183486238,21.5,15.0,89.0,20.14814814814815,20.165254237288135,14.098039215686274,14.130434782608695,28.736842105263158,26.285714285714285,27.470588235294116,31.467157894736843,1.2121212121212122,4.0,17.695652173913043,3.0,31.872093023255815,35.666666666666664,149.0],"type":"choropleth"}],                        {"template":{"data":{"histogram2dcontour":[{"type":"histogram2dcontour","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"choropleth":[{"type":"choropleth","colorbar":{"outlinewidth":0,"ticks":""}}],"histogram2d":[{"type":"histogram2d","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"heatmap":[{"type":"heatmap","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"heatmapgl":[{"type":"heatmapgl","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"contourcarpet":[{"type":"contourcarpet","colorbar":{"outlinewidth":0,"ticks":""}}],"contour":[{"type":"contour","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"surface":[{"type":"surface","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"mesh3d":[{"type":"mesh3d","colorbar":{"outlinewidth":0,"ticks":""}}],"scatter":[{"fillpattern":{"fillmode":"overlay","size":10,"solidity":0.2},"type":"scatter"}],"parcoords":[{"type":"parcoords","line":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterpolargl":[{"type":"scatterpolargl","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"bar":[{"error_x":{"color":"#2a3f5f"},"error_y":{"color":"#2a3f5f"},"marker":{"line":{"color":"#E5ECF6","width":0.5},"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"bar"}],"scattergeo":[{"type":"scattergeo","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterpolar":[{"type":"scatterpolar","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"histogram":[{"marker":{"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"histogram"}],"scattergl":[{"type":"scattergl","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatter3d":[{"type":"scatter3d","line":{"colorbar":{"outlinewidth":0,"ticks":""}},"marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scattermapbox":[{"type":"scattermapbox","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterternary":[{"type":"scatterternary","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scattercarpet":[{"type":"scattercarpet","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"carpet":[{"aaxis":{"endlinecolor":"#2a3f5f","gridcolor":"white","linecolor":"white","minorgridcolor":"white","startlinecolor":"#2a3f5f"},"baxis":{"endlinecolor":"#2a3f5f","gridcolor":"white","linecolor":"white","minorgridcolor":"white","startlinecolor":"#2a3f5f"},"type":"carpet"}],"table":[{"cells":{"fill":{"color":"#EBF0F8"},"line":{"color":"white"}},"header":{"fill":{"color":"#C8D4E3"},"line":{"color":"white"}},"type":"table"}],"barpolar":[{"marker":{"line":{"color":"#E5ECF6","width":0.5},"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"barpolar"}],"pie":[{"automargin":true,"type":"pie"}]},"layout":{"autotypenumbers":"strict","colorway":["#636efa","#EF553B","#00cc96","#ab63fa","#FFA15A","#19d3f3","#FF6692","#B6E880","#FF97FF","#FECB52"],"font":{"color":"#2a3f5f"},"hovermode":"closest","hoverlabel":{"align":"left"},"paper_bgcolor":"white","plot_bgcolor":"#E5ECF6","polar":{"bgcolor":"#E5ECF6","angularaxis":{"gridcolor":"white","linecolor":"white","ticks":""},"radialaxis":{"gridcolor":"white","linecolor":"white","ticks":""}},"ternary":{"bgcolor":"#E5ECF6","aaxis":{"gridcolor":"white","linecolor":"white","ticks":""},"baxis":{"gridcolor":"white","linecolor":"white","ticks":""},"caxis":{"gridcolor":"white","linecolor":"white","ticks":""}},"coloraxis":{"colorbar":{"outlinewidth":0,"ticks":""}},"colorscale":{"sequential":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]],"sequentialminus":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]],"diverging":[[0,"#8e0152"],[0.1,"#c51b7d"],[0.2,"#de77ae"],[0.3,"#f1b6da"],[0.4,"#fde0ef"],[0.5,"#f7f7f7"],[0.6,"#e6f5d0"],[0.7,"#b8e186"],[0.8,"#7fbc41"],[0.9,"#4d9221"],[1,"#276419"]]},"xaxis":{"gridcolor":"white","linecolor":"white","ticks":"","title":{"standoff":15},"zerolinecolor":"white","automargin":true,"zerolinewidth":2},"yaxis":{"gridcolor":"white","linecolor":"white","ticks":"","title":{"standoff":15},"zerolinecolor":"white","automargin":true,"zerolinewidth":2},"scene":{"xaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2},"yaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2},"zaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2}},"shapedefaults":{"line":{"color":"#2a3f5f"}},"annotationdefaults":{"arrowcolor":"#2a3f5f","arrowhead":0,"arrowwidth":1},"geo":{"bgcolor":"white","landcolor":"#E5ECF6","subunitcolor":"white","showland":true,"showlakes":true,"lakecolor":"white"},"title":{"x":0.05},"mapbox":{"style":"light"}}},"geo":{"domain":{"x":[0.0,1.0],"y":[0.0,1.0]},"center":{}},"coloraxis":{"colorbar":{"title":{"text":"avg_cites_per_coauthor"}},"colorscale":[[0.0,"rgb(40, 135, 161)"],[0.16666666666666666,"rgb(121, 167, 172)"],[0.3333333333333333,"rgb(181, 200, 184)"],[0.5,"rgb(237, 234, 194)"],[0.6666666666666666,"rgb(214, 189, 141)"],[0.8333333333333334,"rgb(189, 146, 90)"],[1.0,"rgb(161, 105, 40)"]],"cmid":24.940294951455794,"cmin":0,"cmax":172.33333333333334},"legend":{"tracegroupgap":0},"margin":{"t":30,"l":30,"r":30,"b":30},"height":800,"width":1200,"paper_bgcolor":"LightSteelBlue"},                        {"responsive": true}                    ).then(function(){

var gd = document.getElementById('e3b8c8df-c47c-4c65-8022-67a226b318af');
var x = new MutationObserver(function (mutations, observer) {{
        var display = window.getComputedStyle(gd).display;
        if (!display || display === 'none') {{
            console.log([gd, 'removed!']);
            Plotly.purge(gd);
            observer.disconnect();
        }}
}});

// Listen for the removal of the full notebook cells
var notebookContainer = gd.closest('#notebook-container');
if (notebookContainer) {{
    x.observe(notebookContainer, {childList: true});
}}

// Listen for the clearing of the current output cell
var outputEl = gd.closest('.output');
if (outputEl) {{
    x.observe(outputEl, {childList: true});
}}

                        })                };                });            </script>        </div>



```python
import plotly.express as px
import pandas as pd
import numpy as np

avg_avg_cites_per_coauthor = np.mean(choropleth_df['avg_cites_per_coauthor'])
max_avg_cites_per_coauthor = np.max(choropleth_df['avg_cites_per_coauthor'])

fig = px.choropleth(choropleth_df, locations="country_code",
                    color="avg_cites_per_coauthor",
                    range_color=(0,max_avg_cites_per_coauthor),
                    hover_name="Country",
                    width=1200, height=800,
                    animation_frame="Income group",
                    color_continuous_scale=px.colors.diverging.Earth[::-1],
                    color_continuous_midpoint=avg_avg_cites_per_coauthor)

fig.update_layout(
    margin=dict(l=30, r=30, t=30, b=30),
    paper_bgcolor="LightSteelBlue",
)

fig.show()
```


<div>                            <div id="f9042953-7be8-4f26-97e2-43acc7b533c5" class="plotly-graph-div" style="height:800px; width:1200px;"></div>            <script type="text/javascript">                require(["plotly"], function(Plotly) {                    window.PLOTLYENV=window.PLOTLYENV || {};                                    if (document.getElementById("f9042953-7be8-4f26-97e2-43acc7b533c5")) {                    Plotly.newPlot(                        "f9042953-7be8-4f26-97e2-43acc7b533c5",                        [{"coloraxis":"coloraxis","geo":"geo","hovertemplate":"\u003cb\u003e%{hovertext}\u003c\u002fb\u003e\u003cbr\u003e\u003cbr\u003eIncome group=Low income\u003cbr\u003ecountry_code=%{location}\u003cbr\u003eavg_cites_per_coauthor=%{z}\u003cextra\u003e\u003c\u002fextra\u003e","hovertext":["Afghanistan","Congo, Dem. Rep.","Ethiopia","Mali","Mozambique","Malawi","Rwanda","Sudan","Sierra Leone","Syrian Arab Republic","Chad","Uganda"],"locations":["AFG","COD","ETH","MLI","MOZ","MWI","RWA","SDN","SLE","SYR","TCD","UGA"],"name":"","z":[0.01,1.0,51.25,9.0,14.6,23.666666666666668,10.8,15.666666666666666,0.01,7.0,2.0,28.736842105263158],"type":"choropleth"}],                        {"template":{"data":{"histogram2dcontour":[{"type":"histogram2dcontour","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"choropleth":[{"type":"choropleth","colorbar":{"outlinewidth":0,"ticks":""}}],"histogram2d":[{"type":"histogram2d","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"heatmap":[{"type":"heatmap","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"heatmapgl":[{"type":"heatmapgl","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"contourcarpet":[{"type":"contourcarpet","colorbar":{"outlinewidth":0,"ticks":""}}],"contour":[{"type":"contour","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"surface":[{"type":"surface","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"mesh3d":[{"type":"mesh3d","colorbar":{"outlinewidth":0,"ticks":""}}],"scatter":[{"fillpattern":{"fillmode":"overlay","size":10,"solidity":0.2},"type":"scatter"}],"parcoords":[{"type":"parcoords","line":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterpolargl":[{"type":"scatterpolargl","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"bar":[{"error_x":{"color":"#2a3f5f"},"error_y":{"color":"#2a3f5f"},"marker":{"line":{"color":"#E5ECF6","width":0.5},"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"bar"}],"scattergeo":[{"type":"scattergeo","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterpolar":[{"type":"scatterpolar","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"histogram":[{"marker":{"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"histogram"}],"scattergl":[{"type":"scattergl","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatter3d":[{"type":"scatter3d","line":{"colorbar":{"outlinewidth":0,"ticks":""}},"marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scattermapbox":[{"type":"scattermapbox","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterternary":[{"type":"scatterternary","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scattercarpet":[{"type":"scattercarpet","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"carpet":[{"aaxis":{"endlinecolor":"#2a3f5f","gridcolor":"white","linecolor":"white","minorgridcolor":"white","startlinecolor":"#2a3f5f"},"baxis":{"endlinecolor":"#2a3f5f","gridcolor":"white","linecolor":"white","minorgridcolor":"white","startlinecolor":"#2a3f5f"},"type":"carpet"}],"table":[{"cells":{"fill":{"color":"#EBF0F8"},"line":{"color":"white"}},"header":{"fill":{"color":"#C8D4E3"},"line":{"color":"white"}},"type":"table"}],"barpolar":[{"marker":{"line":{"color":"#E5ECF6","width":0.5},"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"barpolar"}],"pie":[{"automargin":true,"type":"pie"}]},"layout":{"autotypenumbers":"strict","colorway":["#636efa","#EF553B","#00cc96","#ab63fa","#FFA15A","#19d3f3","#FF6692","#B6E880","#FF97FF","#FECB52"],"font":{"color":"#2a3f5f"},"hovermode":"closest","hoverlabel":{"align":"left"},"paper_bgcolor":"white","plot_bgcolor":"#E5ECF6","polar":{"bgcolor":"#E5ECF6","angularaxis":{"gridcolor":"white","linecolor":"white","ticks":""},"radialaxis":{"gridcolor":"white","linecolor":"white","ticks":""}},"ternary":{"bgcolor":"#E5ECF6","aaxis":{"gridcolor":"white","linecolor":"white","ticks":""},"baxis":{"gridcolor":"white","linecolor":"white","ticks":""},"caxis":{"gridcolor":"white","linecolor":"white","ticks":""}},"coloraxis":{"colorbar":{"outlinewidth":0,"ticks":""}},"colorscale":{"sequential":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]],"sequentialminus":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]],"diverging":[[0,"#8e0152"],[0.1,"#c51b7d"],[0.2,"#de77ae"],[0.3,"#f1b6da"],[0.4,"#fde0ef"],[0.5,"#f7f7f7"],[0.6,"#e6f5d0"],[0.7,"#b8e186"],[0.8,"#7fbc41"],[0.9,"#4d9221"],[1,"#276419"]]},"xaxis":{"gridcolor":"white","linecolor":"white","ticks":"","title":{"standoff":15},"zerolinecolor":"white","automargin":true,"zerolinewidth":2},"yaxis":{"gridcolor":"white","linecolor":"white","ticks":"","title":{"standoff":15},"zerolinecolor":"white","automargin":true,"zerolinewidth":2},"scene":{"xaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2},"yaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2},"zaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2}},"shapedefaults":{"line":{"color":"#2a3f5f"}},"annotationdefaults":{"arrowcolor":"#2a3f5f","arrowhead":0,"arrowwidth":1},"geo":{"bgcolor":"white","landcolor":"#E5ECF6","subunitcolor":"white","showland":true,"showlakes":true,"lakecolor":"white"},"title":{"x":0.05},"mapbox":{"style":"light"}}},"geo":{"domain":{"x":[0.0,1.0],"y":[0.0,1.0]},"center":{}},"coloraxis":{"colorbar":{"title":{"text":"avg_cites_per_coauthor"}},"colorscale":[[0.0,"rgb(40, 135, 161)"],[0.16666666666666666,"rgb(121, 167, 172)"],[0.3333333333333333,"rgb(181, 200, 184)"],[0.5,"rgb(237, 234, 194)"],[0.6666666666666666,"rgb(214, 189, 141)"],[0.8333333333333334,"rgb(189, 146, 90)"],[1.0,"rgb(161, 105, 40)"]],"cmid":24.940294951455794,"cmin":0,"cmax":172.33333333333334},"legend":{"tracegroupgap":0},"margin":{"t":30,"l":30,"r":30,"b":30},"height":800,"width":1200,"updatemenus":[{"buttons":[{"args":[null,{"frame":{"duration":500,"redraw":true},"mode":"immediate","fromcurrent":true,"transition":{"duration":500,"easing":"linear"}}],"label":"&#9654;","method":"animate"},{"args":[[null],{"frame":{"duration":0,"redraw":true},"mode":"immediate","fromcurrent":true,"transition":{"duration":0,"easing":"linear"}}],"label":"&#9724;","method":"animate"}],"direction":"left","pad":{"r":10,"t":70},"showactive":false,"type":"buttons","x":0.1,"xanchor":"right","y":0,"yanchor":"top"}],"sliders":[{"active":0,"currentvalue":{"prefix":"Income group="},"len":0.9,"pad":{"b":10,"t":60},"steps":[{"args":[["Low income"],{"frame":{"duration":0,"redraw":true},"mode":"immediate","fromcurrent":true,"transition":{"duration":0,"easing":"linear"}}],"label":"Low income","method":"animate"},{"args":[["Upper middle income"],{"frame":{"duration":0,"redraw":true},"mode":"immediate","fromcurrent":true,"transition":{"duration":0,"easing":"linear"}}],"label":"Upper middle income","method":"animate"},{"args":[["High income"],{"frame":{"duration":0,"redraw":true},"mode":"immediate","fromcurrent":true,"transition":{"duration":0,"easing":"linear"}}],"label":"High income","method":"animate"},{"args":[["Lower middle income"],{"frame":{"duration":0,"redraw":true},"mode":"immediate","fromcurrent":true,"transition":{"duration":0,"easing":"linear"}}],"label":"Lower middle income","method":"animate"}],"x":0.1,"xanchor":"left","y":0,"yanchor":"top"}],"paper_bgcolor":"LightSteelBlue"},                        {"responsive": true}                    ).then(function(){
                            Plotly.addFrames('f9042953-7be8-4f26-97e2-43acc7b533c5', [{"data":[{"coloraxis":"coloraxis","geo":"geo","hovertemplate":"\u003cb\u003e%{hovertext}\u003c\u002fb\u003e\u003cbr\u003e\u003cbr\u003eIncome group=Low income\u003cbr\u003ecountry_code=%{location}\u003cbr\u003eavg_cites_per_coauthor=%{z}\u003cextra\u003e\u003c\u002fextra\u003e","hovertext":["Afghanistan","Congo, Dem. Rep.","Ethiopia","Mali","Mozambique","Malawi","Rwanda","Sudan","Sierra Leone","Syrian Arab Republic","Chad","Uganda"],"locations":["AFG","COD","ETH","MLI","MOZ","MWI","RWA","SDN","SLE","SYR","TCD","UGA"],"name":"","z":[0.01,1.0,51.25,9.0,14.6,23.666666666666668,10.8,15.666666666666666,0.01,7.0,2.0,28.736842105263158],"type":"choropleth"}],"name":"Low income"},{"data":[{"coloraxis":"coloraxis","geo":"geo","hovertemplate":"\u003cb\u003e%{hovertext}\u003c\u002fb\u003e\u003cbr\u003e\u003cbr\u003eIncome group=Upper middle income\u003cbr\u003ecountry_code=%{location}\u003cbr\u003eavg_cites_per_coauthor=%{z}\u003cextra\u003e\u003c\u002fextra\u003e","hovertext":["Albania","Argentina","Armenia","Bulgaria","Bosnia and Herzegovina","Belarus","Brazil","China","Colombia","Costa Rica","Cuba","Dominican Republic","Ecuador","Fiji","Georgia","Indonesia","Iraq","Jamaica","Kazakhstan","Mexico","North Macedonia","Malaysia","Namibia","Peru","West Bank and Gaza","Russian Federation","Serbia","Thailand","Turkmenistan","T\u00fcrkiye","Kosovo","South Africa"],"locations":["ALB","ARG","ARM","BGR","BIH","BLR","BRA","CHN","COL","CRI","CUB","DOM","ECU","FJI","GEO","IDN","IRQ","JAM","KAZ","MEX","MKD","MYS","NAM","PER","PSE","RUS","SRB","THA","TKM","TUR","XKX","ZAF"],"name":"","z":[8.0,44.82142857142857,2.0,7.1,0.5,10.0,26.182440136830103,22.073625549244454,16.528301886792452,32.375,107.33333333333333,1.0,13.0,143.0,32.375,5.615,5.730769230769231,27.75,1.6923076923076923,20.575129533678755,5.166666666666667,22.306122448979593,4.5,5.2,3.0,6.930769230769231,22.408163265306122,14.064220183486238,15.0,20.165254237288135,3.0,31.872093023255815],"type":"choropleth"}],"name":"Upper middle income"},{"data":[{"coloraxis":"coloraxis","geo":"geo","hovertemplate":"\u003cb\u003e%{hovertext}\u003c\u002fb\u003e\u003cbr\u003e\u003cbr\u003eIncome group=High income\u003cbr\u003ecountry_code=%{location}\u003cbr\u003eavg_cites_per_coauthor=%{z}\u003cextra\u003e\u003c\u002fextra\u003e","hovertext":["United Arab Emirates","Australia","Austria","Belgium","Bahrain","Bermuda","Barbados","Brunei Darussalam","Canada","Switzerland","Chile","Cyprus","Czechia","Germany","Denmark","Spain","Estonia","Finland","France","Faroe Islands","United Kingdom","Greece","Greenland","Guyana","Croatia","Hungary","Ireland","Iceland","Israel","Italy","Japan","Korea, Rep.","Kuwait","Lithuania","Luxembourg","Latvia","Monaco","Malta","New Caledonia","Netherlands","Norway","New Zealand","Oman","Panama","Poland","Portugal","Qatar","Romania","Saudi Arabia","Singapore","Slovak Republic","Slovenia","Sweden","Seychelles","Trinidad and Tobago","Uruguay","United States"],"locations":["ARE","AUS","AUT","BEL","BHR","BMU","BRB","BRN","CAN","CHE","CHL","CYP","CZE","DEU","DNK","ESP","EST","FIN","FRA","FRO","GBR","GRC","GRL","GUY","HRV","HUN","IRL","ISL","ISR","ITA","JPN","KOR","KWT","LTU","LUX","LVA","MCO","MLT","NCL","NLD","NOR","NZL","OMN","PAN","POL","PRT","QAT","ROU","SAU","SGP","SVK","SVN","SWE","SYC","TTO","URY","USA"],"name":"","z":[16.45,39.17333333333333,48.95263157894737,28.773662551440328,0.01,8.5,0.01,36.0,29.16759776536313,42.017301038062286,17.535714285714285,60.23076923076923,20.488888888888887,42.99685204616999,33.19469026548673,26.440594059405942,172.33333333333334,25.22748815165877,27.108516483516482,62.5,28.73447946513849,20.80952380952381,26.333333333333332,76.0,13.08695652173913,42.698113207547166,21.93258426966292,23.133333333333333,25.52777777777778,26.73489932885906,20.109615384615385,17.20344827586207,29.714285714285715,14.416666666666666,6.0588235294117645,14.444444444444445,1.0,23.0,0.01,26.811494252873562,31.114427860696516,22.790697674418606,12.375,9.5,14.061827956989248,30.468354430379748,24.318181818181817,8.303571428571429,18.350877192982455,39.60674157303371,21.157894736842106,49.484848484848484,36.09771986970684,31.0,89.0,27.470588235294116,31.467157894736843],"type":"choropleth"}],"name":"High income"},{"data":[{"coloraxis":"coloraxis","geo":"geo","hovertemplate":"\u003cb\u003e%{hovertext}\u003c\u002fb\u003e\u003cbr\u003e\u003cbr\u003eIncome group=Lower middle income\u003cbr\u003ecountry_code=%{location}\u003cbr\u003eavg_cites_per_coauthor=%{z}\u003cextra\u003e\u003c\u002fextra\u003e","hovertext":["Benin","Bangladesh","Bolivia","C\u00f4te d\u2019Ivoire","Cameroon","Cabo Verde","Algeria","Egypt, Arab Rep.","Ghana","India","Iran, Islamic Rep.","Jordan","Kenya","Cambodia","Lao PDR","Lebanon","Sri Lanka","Morocco","Myanmar","Mongolia","Nigeria","Nepal","Pakistan","Philippines","Papua New Guinea","Senegal","Tajikistan","Tunisia","Tanzania","Ukraine","Uzbekistan","Vietnam","Zambia","Zimbabwe"],"locations":["BEN","BGD","BOL","CIV","CMR","CPV","DZA","EGY","GHA","IND","IRN","JOR","KEN","KHM","LAO","LBN","LKA","MAR","MMR","MNG","NGA","NPL","PAK","PHL","PNG","SEN","TJK","TUN","TZA","UKR","UZB","VNM","ZMB","ZWE"],"name":"","z":[10.090909090909092,34.26315789473684,4.0,143.0,3.740740740740741,0.01,12.764705882352942,15.728260869565217,21.403846153846153,26.57304964539007,15.193370165745856,10.96551724137931,61.853658536585364,1.1666666666666667,7.0,26.333333333333332,51.875,10.8125,4.5,22.666666666666668,10.049180327868852,84.86363636363636,26.609865470852018,15.975609756097562,0.01,12.0,21.5,20.14814814814815,14.130434782608695,26.285714285714285,1.2121212121212122,17.695652173913043,35.666666666666664,149.0],"type":"choropleth"}],"name":"Lower middle income"}]);
                        }).then(function(){

var gd = document.getElementById('f9042953-7be8-4f26-97e2-43acc7b533c5');
var x = new MutationObserver(function (mutations, observer) {{
        var display = window.getComputedStyle(gd).display;
        if (!display || display === 'none') {{
            console.log([gd, 'removed!']);
            Plotly.purge(gd);
            observer.disconnect();
        }}
}});

// Listen for the removal of the full notebook cells
var notebookContainer = gd.closest('#notebook-container');
if (notebookContainer) {{
    x.observe(notebookContainer, {childList: true});
}}

// Listen for the clearing of the current output cell
var outputEl = gd.closest('.output');
if (outputEl) {{
    x.observe(outputEl, {childList: true});
}}

                        })                };                });            </script>        </div>



```python
import plotly.express as px
import pandas as pd
import numpy as np

avg_avg_cited_by_sum = np.mean(choropleth_df['cited_by_sum'])
max_avg_cited_by_sum = np.max(choropleth_df['cited_by_sum'])

fig = px.choropleth(choropleth_df, locations="country_code",
                    color="cited_by_sum",
                    range_color=(0,max_avg_cited_by_sum),
                    hover_name="Country",
                    width=1200, height=800,
                    color_continuous_scale=px.colors.diverging.Earth[::-1],
                    color_continuous_midpoint=avg_avg_cited_by_sum)

fig.update_layout(
    margin=dict(l=30, r=30, t=30, b=30),
    paper_bgcolor="LightSteelBlue",
)

fig.write_html(f"plots/cited_by_sum_choropleth-{target_concept}-{n_samples}.html")

fig.show()
```


<div>                            <div id="17f6f86a-0230-48e4-9393-a05e45970eee" class="plotly-graph-div" style="height:800px; width:1200px;"></div>            <script type="text/javascript">                require(["plotly"], function(Plotly) {                    window.PLOTLYENV=window.PLOTLYENV || {};                                    if (document.getElementById("17f6f86a-0230-48e4-9393-a05e45970eee")) {                    Plotly.newPlot(                        "17f6f86a-0230-48e4-9393-a05e45970eee",                        [{"coloraxis":"coloraxis","geo":"geo","hovertemplate":"\u003cb\u003e%{hovertext}\u003c\u002fb\u003e\u003cbr\u003e\u003cbr\u003ecountry_code=%{location}\u003cbr\u003ecited_by_sum=%{z}\u003cextra\u003e\u003c\u002fextra\u003e","hovertext":["Afghanistan","Albania","United Arab Emirates","Argentina","Armenia","Australia","Austria","Belgium","Benin","Bangladesh","Bulgaria","Bahrain","Bosnia and Herzegovina","Belarus","Bermuda","Bolivia","Brazil","Barbados","Brunei Darussalam","Canada","Switzerland","Chile","China","C\u00f4te d\u2019Ivoire","Cameroon","Congo, Dem. Rep.","Colombia","Cabo Verde","Costa Rica","Cuba","Cyprus","Czechia","Germany","Denmark","Dominican Republic","Algeria","Ecuador","Egypt, Arab Rep.","Spain","Estonia","Ethiopia","Finland","Fiji","France","Faroe Islands","United Kingdom","Georgia","Ghana",null,"Greece","Greenland",null,"Guyana","Croatia","Hungary","Indonesia","India","Ireland","Iran, Islamic Rep.","Iraq","Iceland","Israel","Italy","Jamaica","Jordan","Japan","Kazakhstan","Kenya","Cambodia","Korea, Rep.","Kuwait","Lao PDR","Lebanon","Sri Lanka","Lithuania","Luxembourg","Latvia","Morocco","Monaco","Mexico","North Macedonia","Mali","Malta","Myanmar","Mongolia","Mozambique",null,"Malawi","Malaysia","Namibia","New Caledonia","Nigeria","Netherlands","Norway","Nepal","New Zealand","Oman","Pakistan","Panama","Peru","Philippines","Papua New Guinea","Poland","Portugal","West Bank and Gaza","Qatar","Romania","Russian Federation","Rwanda","Saudi Arabia","Sudan","Senegal","Singapore","Sierra Leone","Serbia","Slovak Republic","Slovenia","Sweden","Seychelles","Syrian Arab Republic","Chad","Thailand","Tajikistan","Turkmenistan","Trinidad and Tobago","Tunisia","T\u00fcrkiye",null,"Tanzania","Uganda","Ukraine","Uruguay","United States","Uzbekistan",null,"Vietnam","Kosovo","South Africa","Zambia","Zimbabwe"],"locations":["AFG","ALB","ARE","ARG","ARM","AUS","AUT","BEL","BEN","BGD","BGR","BHR","BIH","BLR","BMU","BOL","BRA","BRB","BRN","CAN","CHE","CHL","CHN","CIV","CMR","COD","COL","CPV","CRI","CUB","CYP","CZE","DEU","DNK","DOM","DZA","ECU","EGY","ESP","EST","ETH","FIN","FJI","FRA","FRO","GBR","GEO","GHA","GLP","GRC","GRL","GUF","GUY","HRV","HUN","IDN","IND","IRL","IRN","IRQ","ISL","ISR","ITA","JAM","JOR","JPN","KAZ","KEN","KHM","KOR","KWT","LAO","LBN","LKA","LTU","LUX","LVA","MAR","MCO","MEX","MKD","MLI","MLT","MMR","MNG","MOZ","MTQ","MWI","MYS","NAM","NCL","NGA","NLD","NOR","NPL","NZL","OMN","PAK","PAN","PER","PHL","PNG","POL","PRT","PSE","QAT","ROU","RUS","RWA","SAU","SDN","SEN","SGP","SLE","SRB","SVK","SVN","SWE","SYC","SYR","TCD","THA","TJK","TKM","TTO","TUN","TUR","TWN","TZA","UGA","UKR","URY","USA","UZB","VEN","VNM","XKX","ZAF","ZMB","ZWE"],"name":"","z":[0,16,658,5020,4,35256,9301,6992,111,1953,71,0,4,60,17,4,22962,0,36,26105,12143,1473,205969,143,101,1,876,0,777,644,783,3688,40976,7502,2,217,312,1447,26705,2068,2050,5323,143,19735,250,30085,518,1113,3,4370,79,75,76,301,2263,1123,18734,1952,5500,149,347,1838,31868,222,318,10457,44,2536,7,9978,208,14,395,415,1038,103,130,519,1,3971,31,18,23,9,68,73,0,71,6558,9,0,613,11663,6254,1867,1960,99,5934,76,156,655,0,5231,9628,18,535,930,1802,54,2092,47,84,3525,0,1098,1206,1633,11082,31,7,2,1533,43,15,89,544,4759,4314,325,546,552,467,149469,40,8,1221,3,5482,321,447],"type":"choropleth"}],                        {"template":{"data":{"histogram2dcontour":[{"type":"histogram2dcontour","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"choropleth":[{"type":"choropleth","colorbar":{"outlinewidth":0,"ticks":""}}],"histogram2d":[{"type":"histogram2d","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"heatmap":[{"type":"heatmap","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"heatmapgl":[{"type":"heatmapgl","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"contourcarpet":[{"type":"contourcarpet","colorbar":{"outlinewidth":0,"ticks":""}}],"contour":[{"type":"contour","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"surface":[{"type":"surface","colorbar":{"outlinewidth":0,"ticks":""},"colorscale":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]]}],"mesh3d":[{"type":"mesh3d","colorbar":{"outlinewidth":0,"ticks":""}}],"scatter":[{"fillpattern":{"fillmode":"overlay","size":10,"solidity":0.2},"type":"scatter"}],"parcoords":[{"type":"parcoords","line":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterpolargl":[{"type":"scatterpolargl","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"bar":[{"error_x":{"color":"#2a3f5f"},"error_y":{"color":"#2a3f5f"},"marker":{"line":{"color":"#E5ECF6","width":0.5},"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"bar"}],"scattergeo":[{"type":"scattergeo","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterpolar":[{"type":"scatterpolar","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"histogram":[{"marker":{"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"histogram"}],"scattergl":[{"type":"scattergl","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatter3d":[{"type":"scatter3d","line":{"colorbar":{"outlinewidth":0,"ticks":""}},"marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scattermapbox":[{"type":"scattermapbox","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scatterternary":[{"type":"scatterternary","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"scattercarpet":[{"type":"scattercarpet","marker":{"colorbar":{"outlinewidth":0,"ticks":""}}}],"carpet":[{"aaxis":{"endlinecolor":"#2a3f5f","gridcolor":"white","linecolor":"white","minorgridcolor":"white","startlinecolor":"#2a3f5f"},"baxis":{"endlinecolor":"#2a3f5f","gridcolor":"white","linecolor":"white","minorgridcolor":"white","startlinecolor":"#2a3f5f"},"type":"carpet"}],"table":[{"cells":{"fill":{"color":"#EBF0F8"},"line":{"color":"white"}},"header":{"fill":{"color":"#C8D4E3"},"line":{"color":"white"}},"type":"table"}],"barpolar":[{"marker":{"line":{"color":"#E5ECF6","width":0.5},"pattern":{"fillmode":"overlay","size":10,"solidity":0.2}},"type":"barpolar"}],"pie":[{"automargin":true,"type":"pie"}]},"layout":{"autotypenumbers":"strict","colorway":["#636efa","#EF553B","#00cc96","#ab63fa","#FFA15A","#19d3f3","#FF6692","#B6E880","#FF97FF","#FECB52"],"font":{"color":"#2a3f5f"},"hovermode":"closest","hoverlabel":{"align":"left"},"paper_bgcolor":"white","plot_bgcolor":"#E5ECF6","polar":{"bgcolor":"#E5ECF6","angularaxis":{"gridcolor":"white","linecolor":"white","ticks":""},"radialaxis":{"gridcolor":"white","linecolor":"white","ticks":""}},"ternary":{"bgcolor":"#E5ECF6","aaxis":{"gridcolor":"white","linecolor":"white","ticks":""},"baxis":{"gridcolor":"white","linecolor":"white","ticks":""},"caxis":{"gridcolor":"white","linecolor":"white","ticks":""}},"coloraxis":{"colorbar":{"outlinewidth":0,"ticks":""}},"colorscale":{"sequential":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]],"sequentialminus":[[0.0,"#0d0887"],[0.1111111111111111,"#46039f"],[0.2222222222222222,"#7201a8"],[0.3333333333333333,"#9c179e"],[0.4444444444444444,"#bd3786"],[0.5555555555555556,"#d8576b"],[0.6666666666666666,"#ed7953"],[0.7777777777777778,"#fb9f3a"],[0.8888888888888888,"#fdca26"],[1.0,"#f0f921"]],"diverging":[[0,"#8e0152"],[0.1,"#c51b7d"],[0.2,"#de77ae"],[0.3,"#f1b6da"],[0.4,"#fde0ef"],[0.5,"#f7f7f7"],[0.6,"#e6f5d0"],[0.7,"#b8e186"],[0.8,"#7fbc41"],[0.9,"#4d9221"],[1,"#276419"]]},"xaxis":{"gridcolor":"white","linecolor":"white","ticks":"","title":{"standoff":15},"zerolinecolor":"white","automargin":true,"zerolinewidth":2},"yaxis":{"gridcolor":"white","linecolor":"white","ticks":"","title":{"standoff":15},"zerolinecolor":"white","automargin":true,"zerolinewidth":2},"scene":{"xaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2},"yaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2},"zaxis":{"backgroundcolor":"#E5ECF6","gridcolor":"white","linecolor":"white","showbackground":true,"ticks":"","zerolinecolor":"white","gridwidth":2}},"shapedefaults":{"line":{"color":"#2a3f5f"}},"annotationdefaults":{"arrowcolor":"#2a3f5f","arrowhead":0,"arrowwidth":1},"geo":{"bgcolor":"white","landcolor":"#E5ECF6","subunitcolor":"white","showland":true,"showlakes":true,"lakecolor":"white"},"title":{"x":0.05},"mapbox":{"style":"light"}}},"geo":{"domain":{"x":[0.0,1.0],"y":[0.0,1.0]},"center":{}},"coloraxis":{"colorbar":{"title":{"text":"cited_by_sum"}},"colorscale":[[0.0,"rgb(40, 135, 161)"],[0.16666666666666666,"rgb(121, 167, 172)"],[0.3333333333333333,"rgb(181, 200, 184)"],[0.5,"rgb(237, 234, 194)"],[0.6666666666666666,"rgb(214, 189, 141)"],[0.8333333333333334,"rgb(189, 146, 90)"],[1.0,"rgb(161, 105, 40)"]],"cmid":5842.628571428571,"cmin":0,"cmax":205969},"legend":{"tracegroupgap":0},"margin":{"t":30,"l":30,"r":30,"b":30},"height":800,"width":1200,"paper_bgcolor":"LightSteelBlue"},                        {"responsive": true}                    ).then(function(){

var gd = document.getElementById('17f6f86a-0230-48e4-9393-a05e45970eee');
var x = new MutationObserver(function (mutations, observer) {{
        var display = window.getComputedStyle(gd).display;
        if (!display || display === 'none') {{
            console.log([gd, 'removed!']);
            Plotly.purge(gd);
            observer.disconnect();
        }}
}});

// Listen for the removal of the full notebook cells
var notebookContainer = gd.closest('#notebook-container');
if (notebookContainer) {{
    x.observe(notebookContainer, {childList: true});
}}

// Listen for the clearing of the current output cell
var outputEl = gd.closest('.output');
if (outputEl) {{
    x.observe(outputEl, {childList: true});
}}

                        })                };                });            </script>        </div>
