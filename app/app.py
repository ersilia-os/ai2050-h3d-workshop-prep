import os
import streamlit as st
import pandas as pd
import numpy as np
from rdkit import Chem
from rdkit.Chem import Draw
import io

st.set_page_config(
    page_title="Ersilia Model Hub - Merge Datasets",
    page_icon=":molecule:",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "..", "data")

MAX_COLUMNS = 10

st.title("🚀 AI2050 Workshop at H3D - Sessions 2.3 & 2.4")
st.markdown("This is a simple app to merge datasets from the [Ersilia Model Hub](https://ersilia.io/model-hub). Feel free to use Excel or any specialized cheminformatics tool for a more advanced analysis!")

if 'datasets' not in st.session_state:
    st.session_state.datasets = {}
if 'files_uploaded' not in st.session_state:
    st.session_state.files_uploaded = False

st.cache_data()
def get_models_metadata():
    df = pd.read_csv(os.path.join(DATA_DIR, "model_metadata.tsv"), sep="\t")
    id2slug = dict(zip(df["model_id"].tolist(), df["slug"].tolist()))
    id2title = dict(zip(df["model_id"].tolist(), df["title"].tolist()))
    return id2slug, id2title

id2slug, id2title = get_models_metadata()

st.sidebar.title("Instructions")
st.sidebar.markdown("""
1. Upload your CSV files.
2. Select your columns of interest.
3. Rank by the primary column of interest.
4. Apply filters based on secondary columns.
5. Visualy inspect the molecules.
""")

@st.cache_data()
def df_columns():
    model_columns = {}
    example_dir = os.path.join(DATA_DIR, "example")
    for fn in os.listdir(example_dir):
        if not fn.startswith("eos"):
            continue
        df = pd.read_csv(os.path.join(example_dir, fn))
        columns = df.columns.tolist()
        columns = [c for c in columns if c not in ["input", "key", "smiles"]]
        columns = [c for c in columns if "drugbank_approved_percentile" not in c]
        model_id = fn.split(".")[0]
        model_columns[model_id] = columns
    return model_columns

model_columns = df_columns()

def resolve_model_id_of_df(df):
    columns = df.columns.tolist()
    columns = [c for c in columns if c not in ["input", "key", "smiles"]]
    columns = [c for c in columns if "drugbank_approved_percentile" not in c]
    ncol = len(columns)
    for k,v in model_columns.items():
        if v[:1] == columns[:1]:
            return k, df[columns]
    if ncol == 1:
        smi_0 = list(df.columns)[0]
        smiles_list = [smi_0] + df[smi_0].tolist()
        df = pd.DataFrame(smiles_list, columns=["smiles"])
        return "input", df
    else:
        return None, None

if not st.session_state.files_uploaded:

    uploaded_files = st.sidebar.file_uploader(
        "Choose your CSV files",
        type=["csv"],
        accept_multiple_files=True
    )

    if uploaded_files and st.sidebar.button("Upload files"):
        uploaded_data = []
        uploaded_labels = []
        if len(uploaded_files) > 5:
            st.sidebar.warning("You can only upload up to 5 files at a time. Please remove some files and try again. For now, only the first 5 files are processed.")
        for uploaded_file in uploaded_files:
            if uploaded_file.name not in st.session_state.datasets:
                df = pd.read_csv(uploaded_file)
                label, df = resolve_model_id_of_df(df)
                if label is None:
                    st.sidebar.error(f"Could not resolve file type '{uploaded_file.name}'. Please ensure the file has the correct format.")
                    continue
                st.session_state.datasets[uploaded_file.name] = (label, df)
                st.sidebar.success(f"File '{uploaded_file.name}' uploaded successfully!")
            else:
                st.sidebar.warning(f"File '{uploaded_file.name}' already exists in the session state.")
        st.session_state.files_uploaded = True

else:

    st.sidebar.success("Files already uploaded.")
    if st.sidebar.button("Reset uploads"):
        st.session_state.datasets.clear()
        st.session_state.files_uploaded = False
        st.rerun()


if not st.session_state.datasets:
    st.sidebar.info("No datasets uploaded yet. Please upload CSV files to merge datasets from the Ersilia Model Hub.")
else:
    datasets = {}
    for k,v in st.session_state.datasets.items():
        label, df = v
        datasets[label] = df
    if "input" not in datasets:
        st.error("No input dataset found. Please upload a dataset containing molecules in SMILES format.")
    else:
        if len(datasets) == 1:
            st.sidebar.info("Only the input dataset is available. Please upload additional datasets to merge.")
        else:
            all_columns = []
            for k,v in datasets.items():
                if k == "input":
                    continue
                else:
                    columns_rename = {col: f"{k} - {col}" for col in v.columns}
                    df = v.rename(columns=columns_rename)
                    datasets[k] = df
                    all_columns += df.columns.tolist()
            
            selected_columns = st.multiselect("Select columns to merge", options=all_columns, default=[])
            if len(selected_columns) > MAX_COLUMNS:
                st.warning(f"You can only select up to {MAX_COLUMNS} columns for your selection. The first {MAX_COLUMNS} columns are kept for downstream analysis.")
                selected_columns = selected_columns[:MAX_COLUMNS]
            
            st.cache_data()
            def molecule_dictionary(df):
                mol_dict = {}
                for smiles in df["smiles"].tolist():
                    mol = Chem.MolFromSmiles(smiles)
                    mol_dict[smiles] = mol
                return mol_dict
            
            mol_dict = molecule_dictionary(datasets["input"])

            df = datasets["input"].copy()
            identifiers = ["cpd_{0}".format(i+1) for i in range(len(df))]
            smi2id = {}
            for i, smiles in enumerate(df["smiles"].tolist()):
                smi2id[smiles] = identifiers[i]
            df["cpd_num"] = identifiers
            df = df[["cpd_num", "smiles"]]
            for col in selected_columns:
                model_id = col.split(" - ")[0]
                series = datasets[model_id][col]
                df[col] = series

            mol_dict = molecule_dictionary(df)

            df_ = df.copy()
            df_ = df_[["cpd_num", "smiles"] + selected_columns]

            cols = st.columns(int(MAX_COLUMNS/2))
            for i, column in enumerate(selected_columns[:int(MAX_COLUMNS/2)]):
                min_val, max_val = np.min(df[column]), np.max(df[column])
                col = cols[i]
                min_val, max_val = col.slider(column, min_val, max_val, (min_val, max_val))
                df_ = df_[df_[column] >= min_val]
                df_ = df_[df_[column] <= max_val]

            for i, column in enumerate(selected_columns[int(MAX_COLUMNS/2):]):
                min_val, max_val = np.min(df[column]), np.max(df[column])
                col = cols[i]
                min_val, max_val = col.slider(column, min_val, max_val, (min_val, max_val))
                df_ = df_[df_[column] >= min_val]
                df_ = df_[df_[column] <= max_val]

            
            st.dataframe(df_)

            st.subheader("Selected Molecules (up to 25)")

            smiles_list = st.text_area("Paste your SMILES here (one per line)", height=200, key="smiles_input").split("\n")
            if len(smiles_list) > 25:
                st.warning("You can only display up to 25 molecules. The first 25 will be displayed.")
                smiles_list = smiles_list[:25]
            smiles_list = [smiles.strip() for smiles in smiles_list if smiles != ""]

            if not smiles_list:
                st.warning("No SMILES provided. Please paste your SMILES in the text area above.")
            else:
                mols = []
                cpd_nums = []
                for smiles in smiles_list:
                    if smiles not in mol_dict:
                        st.warning(f"SMILES '{smiles}' not found in the dataset. Please check your input.")
                        continue
                    mols += [mol_dict[smiles]]
                    cpd_nums += [smi2id[smiles]]

                def mols_to_grid_image(mols, molsPerRow=5, subImgSize=(300,300)):
                    img = Draw.MolsToGridImage(
                        mols, 
                        molsPerRow=molsPerRow, 
                        subImgSize=subImgSize, 
                        legends=cpd_nums[:25]
                    )
                    return img

                if mols:
                    grid_img = mols_to_grid_image(mols[:25]) 
                    buf = io.BytesIO()
                    grid_img.save(buf, format="PNG")
                    st.image(buf.getvalue())
                else:
                    st.info("No molecules to display.")

with st.sidebar:
    st.image(
        os.path.join(ROOT, "..", "assets", "schmidt_sciences_logo.png"),
        use_container_width=True,
        caption="Workshop supported by AI2050 Schmidt Sciences"
    )

with st.sidebar:
    st.image(
        os.path.join(ROOT, "..", "assets", "ersilia_brand.png"),
        use_container_width=True,
        caption="Designed with ❤️ by the Ersilia Open Source Initiative"
    )