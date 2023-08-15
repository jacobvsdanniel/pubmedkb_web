color_node_query = "#d5abff";  // 270°, 33%, 100% violet
color_node_sub = "#abffff";  // 180°, 33%, 100% cyan
color_node_super = "#d5ffab";  // 90°, 33%, 100% yellow-green
color_node_sibling = "#ffffab";  // 60°, 33%, 100% yellow
color_node_supplemental = "#ffd5ab";  // 30°, 33%, 100% orange
color_node_descriptor = "#ffabab";  // 0°, 33%, 100% red

color_edge_query = "#8945cc";  // 270°, 66%, 80% violet
color_edge_sub = "#45cccc";  // 180°, 66%, 80% cyan
color_edge_super = "#89cc45";  // 90°, 66%, 80% yellow-green
color_edge_sibling = "#cccc45";  // 60°, 66%, 80% yellow
color_edge_supplemental = "#cc8945";  // 30°, 66%, 80% orange
color_edge_descriptor = "#cc4545";  // 0°, 66%, 80% red

length_edge_query = 300;
length_edge_sub = 120;
length_edge_super = 300;
length_edge_sibling = 120;
length_edge_supplemental = 120;
length_edge_descriptor = 120;

nodes = new vis.DataSet([
    {"id": -1, "label": "query", "color": color_node_query},
    {"id": -2, "label": "sub-category", "color": color_node_sub},
    {"id": -3, "label": "sub-category", "color": color_node_sub},
    {"id": -4, "label": "sub-category", "color": color_node_sub},
    {"id": -5, "label": "super-category", "color": color_node_super},
    {"id": -6, "label": "super-category", "color": color_node_super},
    {"id": -7, "label": "super-category", "color": color_node_super},
    {"id": -8, "label": "sibling", "color": color_node_sibling},
    {"id": -9, "label": "sibling", "color": color_node_sibling},
    {"id": -10, "label": "supplemental", "color": color_node_supplemental},
    {"id": -11, "label": "supplemental", "color": color_node_supplemental},
    {"id": -12, "label": "supplemental", "color": color_node_supplemental},
]);

edges = new vis.DataSet([
    {"from": -1, "to": -2, "length": length_edge_sub, "color": color_edge_sub, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -1, "to": -3, "length": length_edge_sub, "color": color_edge_sub, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -1, "to": -4, "length": length_edge_sub, "color": color_edge_sub, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -5, "to": -1, "length": length_edge_query, "color": color_edge_query, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -6, "to": -1, "length": length_edge_query, "color": color_edge_query, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -7, "to": -5, "length": length_edge_super, "color": color_edge_super, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -7, "to": -6, "length": length_edge_super, "color": color_edge_super, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -5, "to": -8, "length": length_edge_sibling, "color": color_edge_sibling, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -6, "to": -9, "length": length_edge_sibling, "color": color_edge_sibling, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -1, "to": -10, "length": length_edge_supplemental, "color": color_edge_supplemental, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -6, "to": -11, "length": length_edge_supplemental, "color": color_edge_supplemental, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
    {"from": -8, "to": -12, "length": length_edge_supplemental, "color": color_edge_supplemental, "arrows": {"to": {"enabled": true, "type": "arrow"}}},
]);

container = document.getElementById("div_graph");
data = {
    nodes: nodes,
    edges: edges,
};
options = {};
network = new vis.Network(container, data, options);

function run_show_default_query(){
    select_query_type = document.getElementById("select_query_type").value;

    if (select_query_type == "mesh") {
        query = "MESH:D013964";
    } else if (select_query_type == "mesh_name") {
        query = "Hearing Loss";
    } else if (select_query_type == "hpo") {
        query = "HP_0000704";
    } else if (select_query_type == "hpo_name") {
        query = "Gingival hyperplasia";
    } else if (select_query_type == "literature_name") {
        query = "carcinoma of the thyroid";
    } else if (select_query_type == "all_name") {
        query = "thyroid cancer";
    }

    input_query = document.getElementById("input_query");
    input_query.value = query;
}

function run_query(){
    document.getElementById("div_status").innerHTML = "Loading...";

    request_data = {
        "query_type": document.getElementById("select_query_type").value,
        "query": document.getElementById("input_query").value,
        "super_level": document.getElementById("input_super_level").value,
        "sub_level": document.getElementById("input_sub_level").value,
        "sibling_level": document.getElementById("select_sibling_level").value,
        "supplemental_level": document.getElementById("select_supplemental_level").value,
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
    query_type = document.getElementById("select_query_type").value;
    query = document.getElementById("input_query").value;
    super_level = document.getElementById("input_super_level").value;
    sub_level = document.getElementById("input_sub_level").value;
    sibling_level = document.getElementById("select_sibling_level").value;
    supplemental_level = document.getElementById("select_supplemental_level").value;

    query_type = encodeURIComponent(query_type)
    query = encodeURIComponent(query)
    super_level = encodeURIComponent(super_level)
    sub_level = encodeURIComponent(sub_level)
    sibling_level = encodeURIComponent(sibling_level)
    supplemental_level = encodeURIComponent(supplemental_level)

    url = `./query_mesh_disease?query_type=${query_type}`
    url = `${url}&query=${query}`
    url = `${url}&super_level=${super_level}`
    url = `${url}&sub_level=${sub_level}`
    url = `${url}&sibling_level=${sibling_level}`
    url = `${url}&supplemental_level=${supplemental_level}`

    window.open(url, "_blank");
}
