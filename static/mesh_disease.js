violet = "#d5abff";
cyan = "#abffff";
yellow_green = "#d5ffab";
yellow = "#ffffab";
orange = "#ffd5ab";
red = "#ffabab";

nodes = new vis.DataSet([
    {"id": -1, "label": "query", "color": violet},
    {"id": -2, "label": "sub-category", "color": cyan},
    {"id": -3, "label": "sub-category", "color": cyan},
    {"id": -4, "label": "sub-category", "color": cyan},
    {"id": -5, "label": "super-category", "color": yellow_green},
    {"id": -6, "label": "super-category", "color": yellow_green},
    {"id": -7, "label": "super-category", "color": yellow_green},
    {"id": -8, "label": "sibling", "color": yellow},
    {"id": -9, "label": "sibling", "color": yellow},
    {"id": -10, "label": "supplemental", "color": orange},
    {"id": -11, "label": "supplemental", "color": orange},
    {"id": -12, "label": "supplemental", "color": orange},
]);

edges = new vis.DataSet([
    {"from": -1, "to": -2, "length": 100, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -1, "to": -3, "length": 100, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -1, "to": -4, "length": 100, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -5, "to": -1, "length": 100, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -6, "to": -1, "length": 100, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -7, "to": -5, "length": 100, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -7, "to": -6, "length": 100, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -5, "to": -8, "length": 100, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -6, "to": -9, "length": 100, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -1, "to": -10, "length": 100, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -6, "to": -11, "length": 100, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -8, "to": -12, "length": 100, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
]);

container = document.getElementById("div_graph");
data = {
    nodes: nodes,
    edges: edges,
};
options = {};
network = new vis.Network(container, data, options);

function run_show_default_query(){
    sl_query_type = document.getElementById("sl_query_type").value;

    if (sl_query_type == "mesh") {
        query = "MESH:D013964";
    } else if (sl_query_type == "mesh_name") {
        query = "Hearing Loss";
    } else if (sl_query_type == "hpo") {
        query = "HP_0000704";
    } else if (sl_query_type == "hpo_name") {
        query = "Gingival hyperplasia";
    } else if (sl_query_type == "literature_name") {
        query = "carcinoma of the thyroid";
    } else if (sl_query_type == "all_name") {
        query = "thyroid cancer";
    }

    input_query = document.getElementById("input_query");
    input_query.value = query;
}

function run_query(){
    document.getElementById("div_status").innerHTML = "Loading...";

    request_data = {
        "query_type": document.getElementById("sl_query_type").value,
        "query": document.getElementById("input_query").value,
        "super_level": document.getElementById("ta_super_level").value,
        "sub_level": document.getElementById("ta_sub_level").value,
        "sub_nodes": document.getElementById("ta_sub_nodes").value,
        "sibling_nodes": document.getElementById("ta_sibling_nodes").value,
        "supplemental_nodes": document.getElementById("ta_supplemental_nodes").value,
    };

    fetch("./run_mesh_disease", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        document.getElementById("div_result").innerHTML = response_data["result"];

        node_list = response_data["node_list"];
        edge_list = response_data["edge_list"];

        network.destroy();

        container = document.getElementById("div_graph");
        data = {
            nodes: new vis.DataSet(node_list),
            edges: new vis.DataSet(edge_list),
        };
        options = {};
        network = new vis.Network(container, data, options);

        document.getElementById("div_status").innerHTML = "Ready";
    })
}

function get_json(){
    query_type = document.getElementById("sl_query_type").value;
    query = document.getElementById("input_query").value;
    super_level = document.getElementById("ta_super_level").value;
    sub_level = document.getElementById("ta_sub_level").value;
    sub_nodes = document.getElementById("ta_sub_nodes").value;
    sibling_nodes = document.getElementById("ta_sibling_nodes").value;
    supplemental_nodes = document.getElementById("ta_supplemental_nodes").value;

    query_type = encodeURIComponent(query_type)
    query = encodeURIComponent(query)
    super_level = encodeURIComponent(super_level)
    sub_level = encodeURIComponent(sub_level)
    sub_nodes = encodeURIComponent(sub_nodes)
    sibling_nodes = encodeURIComponent(sibling_nodes)
    supplemental_nodes = encodeURIComponent(supplemental_nodes)

    url = `./query_mesh_disease?query_type=${query_type}`
    url = `${url}&query=${query}`
    url = `${url}&super_level=${super_level}`
    url = `${url}&sub_level=${sub_level}`
    url = `${url}&sub_nodes=${sub_nodes}`
    url = `${url}&sibling_nodes=${sibling_nodes}`
    url = `${url}&supplemental_nodes=${supplemental_nodes}`

    window.open(url, "_blank");
}
