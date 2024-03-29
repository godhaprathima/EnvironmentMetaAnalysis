# Version  = 1.0v
# Jerin Thomas - 06/28/23

# -*- coding: utf-8 -*-
"""Network Graph.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1AhM_SGIINNN4Cjz6EBcr4NJnbUF-RLhn
"""

import pandas as pd

!pip install pyalex

import pyalex
import requests

query = pyalex.Works().filter(primary_location={"source":{"id":"S13479253"}}) \
                          .paginate(per_page=25, n_max=100000)

documents = []
for page in query:
    for doc in page:
        documents.append(doc)

latest_documents = []
for i in documents:
    if i['publication_year'] >= 2013:
        latest_documents.append(i)

latest_documents[1]['authorships']

import requests

api_url = "https://api.openalex.org/authors?filter=last_known_institution.is_global_south:true&group-by=last_known_institution.country_code"

try:
    response = requests.get(api_url)
    data = response.json()

    # Process the data to fetch 'key' and 'key_display_name' and print them
    # for item in data['group_by']:
    #     key = item['key']
    #     key_display_name = item['key_display_name']
    #     print(f"Key: {key}, Key Display Name: {key_display_name}")
except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")

data['group_by']

country_codes = {}
for i in data['group_by']:
  country_codes[i['key']] = i['key_display_name']

country_codes

final = []
for i in range(len(latest_documents)):
  d = {}
  for j in range(len(latest_documents[i]['authorships'])):
    if 'institutions' in latest_documents[i]['authorships'][j].keys():
      if len(latest_documents[i]['authorships'][j]['institutions']) > 0:
        if 'country_code' in latest_documents[i]['authorships'][j]['institutions'][0].keys():
          code = latest_documents[i]['authorships'][j]['institutions'][0]['country_code']
          if code in country_codes.keys():
            d[latest_documents[i]['authorships'][j]['author']['display_name']] = country_codes[code]
    if len(d)>0:
      final.append(d)

len(final)

final

import networkx as nx
import matplotlib.pyplot as plt

def create_network_graph(data):
    # Create a new graph
    graph = nx.Graph()

    # Iterate through each dictionary in the data
    for item in data:
        # Get the unique countries in the dictionary
        countries = set(item.values())

        # Add nodes for each country with sizes based on the number of authors
        for country in countries:
            authors_count = sum(value == country for value in item.values())
            graph.add_node(country, size=authors_count)

        # Connect authors from different countries
        authors = list(item.keys())
        for i in range(len(authors)):
            for j in range(i + 1, len(authors)):
                if item[authors[i]] != item[authors[j]]:
                    graph.add_edge(item[authors[i]], item[authors[j]], color='red')

    # Find isolated nodes (countries) with no edges
    isolated_nodes = [node for node, degree in dict(graph.degree()).items() if degree == 0]

    # Remove isolated nodes from the graph
    graph.remove_nodes_from(isolated_nodes)

    # Set the background color to white
    plt.rcParams['axes.facecolor'] = 'white'

    # Expand the figure size for better visibility
    plt.figure(figsize=(10, 8))

    # Draw the graph with node sizes and red edges
    pos = nx.spring_layout(graph, seed=42, k=0.3, iterations=50)
    sizes = [graph.nodes[node]['size'] * 200 for node in graph.nodes()]
    colors = [graph.edges[edge]['color'] for edge in graph.edges()]
    nx.draw(graph, pos, node_size=sizes, edge_color=colors, with_labels=True)

    # Show the graph
    plt.show()


create_network_graph(final)

import networkx as nx
import matplotlib.pyplot as plt

def display_country_connections(data, target_country):
    # Create a new graph
    graph = nx.Graph()

    # Iterate through each dictionary in the data
    for item in data:
        # Get the unique countries in the dictionary
        countries = set(item.values())

        # Add nodes for each country with sizes based on the number of authors
        for country in countries:
            authors_count = sum(value == country for value in item.values())
            graph.add_node(country, size=authors_count)

    # Connect authors from different countries to the target country
    for item in data:
        if target_country in item.values():
            connected_countries = set()
            for author, country in item.items():
                if country != target_country:
                    connected_countries.add(country)

            for country in connected_countries:
                graph.add_edge(target_country, country, color='red')

    # Find isolated nodes (countries) with no edges
    isolated_nodes = [node for node, degree in dict(graph.degree()).items() if degree == 0]

    # Remove isolated nodes from the graph
    graph.remove_nodes_from(isolated_nodes)

    # Set the background color to white
    plt.rcParams['axes.facecolor'] = 'white'

    # Expand the figure size for better visibility
    plt.figure(figsize=(10, 8))

    # Draw the graph with node sizes and red edges
    pos = nx.spring_layout(graph, seed=42, k=0.3, iterations=50)
    sizes = [graph.nodes[node]['size'] * 200 for node in graph.nodes()]
    colors = ['blue' if node == target_country else 'cyan' for node in graph.nodes()]
    nx.draw(graph, pos, node_size=sizes, node_color=colors, edge_color='cyan', with_labels=True)

    # Show the graph
    plt.show()


target_country = 'India'
display_country_connections(final, target_country)

