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
    {"from": -1, "to": -2, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -1, "to": -3, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -1, "to": -4, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -5, "to": -1, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -6, "to": -1, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -7, "to": -5, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -7, "to": -6, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -5, "to": -8, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -6, "to": -9, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -1, "to": -10, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -6, "to": -11, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -8, "to": -12, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
]);

container = document.getElementById("div_graph");
data = {
    nodes: nodes,
    edges: edges,
};
options = {};
network = new vis.Network(container, data, options);


function run_query(){
    document.getElementById("div_status").innerHTML = "Loading...";

    request_data = {
        "query_type": document.getElementById("sl_query_type").value,
        "query_id": document.getElementById("ta_query_id").value,
        "query_term": document.getElementById("ta_query_term").value,
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
    query_id = document.getElementById("ta_query_id").value;
    query_term = document.getElementById("ta_query_term").value;
    super_level = document.getElementById("ta_super_level").value;
    sub_level = document.getElementById("ta_sub_level").value;
    sub_nodes = document.getElementById("ta_sub_nodes").value;
    sibling_nodes = document.getElementById("ta_sibling_nodes").value;
    supplemental_nodes = document.getElementById("ta_supplemental_nodes").value;

    query_type = encodeURIComponent(query_type)
    query_id = encodeURIComponent(query_id)
    query_term = encodeURIComponent(query_term)
    super_level = encodeURIComponent(super_level)
    sub_level = encodeURIComponent(sub_level)
    sub_nodes = encodeURIComponent(sub_nodes)
    sibling_nodes = encodeURIComponent(sibling_nodes)
    supplemental_nodes = encodeURIComponent(supplemental_nodes)

    url = `./query_mesh_disease?query_type=${query_type}`
    url = `${url}&query_id=${query_id}`
    url = `${url}&query_term=${query_term}`
    url = `${url}&super_level=${super_level}`
    url = `${url}&sub_level=${sub_level}`
    url = `${url}&sub_nodes=${sub_nodes}`
    url = `${url}&sibling_nodes=${sibling_nodes}`
    url = `${url}&supplemental_nodes=${supplemental_nodes}`

    window.open(url, "_blank");
}
